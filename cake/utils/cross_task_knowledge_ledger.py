#!/usr/bin/env python3
"""cross_task_knowledge_ledger.py - Institutional Memory for CAKE

Maintains cross-project knowledge including successful strategies, domain patterns,
anti-patterns, solution templates, and heuristics. Enables Claude to leverage
accumulated wisdom from all previous tasks across domains and contexts.

Author: CAKE Team
License: MIT
Python: 3.11+
"""
import hashlib
import json
import logging
import re
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

    # Mock classes for when sklearn is not available
    class TfidfVectorizer:
        def __init__(self, **kwargs):
            pass

        def fit_transform(self, texts):
            return None

        def transform(self, texts):
            return None

    def cosine_similarity(a, b):
        return [[0.5]]


try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

    # Mock networkx when not available
    class nx:
        @staticmethod
        def DiGraph():
            return type(
                "DiGraph",
                (),
                {
                    "add_node": lambda self, *args, **kwargs: None,
                    "add_edge": lambda self, *args, **kwargs: None,
                    "nodes": lambda self: [],
                },
            )()


# Configure module logger
logger = logging.getLogger(__name__)


class KnowledgeType(Enum):
    """Types of knowledge stored in the ledger."""

    STRATEGY_PATTERN = auto()  # Successful strategy sequences
    SOLUTION_TEMPLATE = auto()  # Reusable solution patterns
    ANTI_PATTERN = auto()  # Known failure patterns to avoid
    DOMAIN_HEURISTIC = auto()  # Domain-specific rules of thumb
    TOOL_PREFERENCE = auto()  # Tool/library preferences by context
    ERROR_RESOLUTION = auto()  # Error → solution mappings
    OPTIMIZATION_RULE = auto()  # Performance optimization patterns
    QUALITY_GATE = auto()  # Quality requirements by domain


@dataclass
class KnowledgeEntry:
    """
    A single piece of cross-task knowledge.

    Attributes:
        knowledge_id: Unique identifier
        knowledge_type: Type of knowledge
        content: The actual knowledge content
        context_tags: Tags describing when this applies
        success_metrics: Quantified success data
        confidence_score: 0.0-1.0 confidence in this knowledge
        usage_count: How many times this has been applied
        last_success: When this was last successfully used
        source_tasks: Tasks this knowledge came from
        domain_applicability: Which domains this applies to
        prerequisites: What conditions must be met to use this
        metadata: Additional structured data
    """

    knowledge_id: str
    knowledge_type: KnowledgeType
    content: Dict[str, Any]
    context_tags: Set[str]
    success_metrics: Dict[str, float]
    confidence_score: float
    usage_count: int = 0
    last_success: Optional[datetime] = None
    source_tasks: Set[str] = field(default_factory=set)
    domain_applicability: Set[str] = field(default_factory=set)
    prerequisites: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["knowledge_type"] = self.knowledge_type.name
        data["context_tags"] = list(self.context_tags)
        data["source_tasks"] = list(self.source_tasks)
        data["domain_applicability"] = list(self.domain_applicability)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        if self.last_success:
            data["last_success"] = self.last_success.isoformat()
        return data


@dataclass
class TaskSummary:
    """
    Summary of a completed task for knowledge extraction.

    Attributes:
        task_id: Unique task identifier
        description: Original task description
        domain: Domain this task belonged to
        final_status: How the task concluded
        stage_sequence: Sequence of stages executed
        strategies_used: Strategic decisions made
        tools_used: Tools and libraries used
        errors_encountered: Errors that occurred
        solutions_applied: Solutions that worked
        quality_metrics: Final quality measurements
        performance_metrics: Performance data
        cost_metrics: Cost and efficiency data
        duration: Total time taken
        artifacts_produced: Final deliverables
        lessons_learned: Explicit lessons identified
    """

    task_id: str
    description: str
    domain: str
    final_status: str
    stage_sequence: List[str]
    strategies_used: List[Dict[str, Any]]
    tools_used: Set[str]
    errors_encountered: List[Dict[str, Any]]
    solutions_applied: List[Dict[str, Any]]
    quality_metrics: Dict[str, float]
    performance_metrics: Dict[str, float]
    cost_metrics: Dict[str, float]
    duration: float
    artifacts_produced: List[str]
    lessons_learned: List[str]
    completed_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeExtractor:
    """
    Extracts reusable knowledge from completed tasks.
    """

    def __init__(self):
        """Initialize knowledge extractor."""
        self.strategy_patterns = []
        self.solution_templates = []
        self.error_patterns = {}

        # TF-IDF vectorizer for text similarity
        self.text_vectorizer = TfidfVectorizer(
            max_features=1000, stop_words="english", ngram_range=(1, 2)
        )

    def extract_knowledge(self, task_summary: TaskSummary) -> List[KnowledgeEntry]:
        """
        Extract all types of knowledge from a completed task.

        Args:
            task_summary: Summary of the completed task

        Returns:
            List of extracted knowledge entries
        """
        knowledge_entries = []

        # Extract different types of knowledge
        knowledge_entries.extend(self._extract_strategy_patterns(task_summary))
        knowledge_entries.extend(self._extract_solution_templates(task_summary))
        knowledge_entries.extend(self._extract_anti_patterns(task_summary))
        knowledge_entries.extend(self._extract_domain_heuristics(task_summary))
        knowledge_entries.extend(self._extract_tool_preferences(task_summary))
        knowledge_entries.extend(self._extract_error_resolutions(task_summary))
        knowledge_entries.extend(self._extract_optimization_rules(task_summary))
        knowledge_entries.extend(self._extract_quality_gates(task_summary))

        logger.info(
            f"Extracted {len(knowledge_entries)} knowledge entries from task {task_summary.task_id}"
        )

        return knowledge_entries

    def _extract_strategy_patterns(self, task: TaskSummary) -> List[KnowledgeEntry]:
        """Extract successful strategy patterns."""
        entries = []

        if task.final_status == "success" and len(task.stage_sequence) > 3:
            # Identify successful strategy sequences
            strategy_sequence = [
                s["action"] for s in task.strategies_used if "action" in s
            ]

            if len(strategy_sequence) >= 3:
                # Extract patterns of length 3-5
                for length in range(3, min(6, len(strategy_sequence) + 1)):
                    for i in range(len(strategy_sequence) - length + 1):
                        pattern = strategy_sequence[i : i + length]

                        knowledge_id = self._generate_knowledge_id(
                            "strategy_pattern", "_".join(pattern)
                        )

                        entry = KnowledgeEntry(
                            knowledge_id=knowledge_id,
                            knowledge_type=KnowledgeType.STRATEGY_PATTERN,
                            content={
                                "pattern": pattern,
                                "stage_context": (
                                    task.stage_sequence[i : i + length]
                                    if i + length <= len(task.stage_sequence)
                                    else task.stage_sequence[i:]
                                ),
                                "success_context": {
                                    "domain": task.domain,
                                    "task_type": self._categorize_task(
                                        task.description
                                    ),
                                    "complexity": self._estimate_complexity(task),
                                },
                            },
                            context_tags=self._generate_context_tags(task, pattern),
                            success_metrics={
                                "task_success_rate": 1.0,
                                "efficiency_score": self._calculate_efficiency(task),
                                "quality_score": task.quality_metrics.get(
                                    "overall_score", 0.8
                                ),
                            },
                            confidence_score=self._calculate_pattern_confidence(
                                task, pattern
                            ),
                            source_tasks={task.task_id},
                            domain_applicability={task.domain},
                        )
                        entries.append(entry)

        return entries

    def _extract_solution_templates(self, task: TaskSummary) -> List[KnowledgeEntry]:
        """Extract reusable solution templates."""
        entries = []

        if task.final_status == "success" and task.artifacts_produced:
            # Extract solution patterns from artifacts
            for artifact in task.artifacts_produced:
                template = self._extract_template_from_artifact(artifact, task)

                if template:
                    knowledge_id = self._generate_knowledge_id(
                        "solution_template", template["template_type"]
                    )

                    entry = KnowledgeEntry(
                        knowledge_id=knowledge_id,
                        knowledge_type=KnowledgeType.SOLUTION_TEMPLATE,
                        content=template,
                        context_tags=self._generate_context_tags(
                            task, [template["template_type"]]
                        ),
                        success_metrics={
                            "reusability_score": template.get("reusability_score", 0.7),
                            "quality_score": task.quality_metrics.get(
                                "code_quality", 0.8
                            ),
                        },
                        confidence_score=0.8,
                        source_tasks={task.task_id},
                        domain_applicability={task.domain},
                    )
                    entries.append(entry)

        return entries

    def _extract_anti_patterns(self, task: TaskSummary) -> List[KnowledgeEntry]:
        """Extract anti-patterns from failed attempts."""
        entries = []

        # Look for patterns that led to failures
        for error in task.errors_encountered:
            if error.get("resolution_attempts", 0) > 2:
                # Multiple failed attempts indicate an anti-pattern
                anti_pattern = {
                    "pattern_type": "repeated_failure",
                    "error_signature": error.get("error_type", "unknown"),
                    "failed_strategies": error.get("failed_strategies", []),
                    "context": {
                        "stage": error.get("stage"),
                        "domain": task.domain,
                        "error_details": error.get("message", "")[:200],
                    },
                }

                knowledge_id = self._generate_knowledge_id(
                    "anti_pattern",
                    f"{anti_pattern['error_signature']}_{anti_pattern['pattern_type']}",
                )

                entry = KnowledgeEntry(
                    knowledge_id=knowledge_id,
                    knowledge_type=KnowledgeType.ANTI_PATTERN,
                    content=anti_pattern,
                    context_tags=self._generate_context_tags(
                        task, [anti_pattern["error_signature"]]
                    ),
                    success_metrics={"avoidance_value": 0.8},
                    confidence_score=0.7,
                    source_tasks={task.task_id},
                    domain_applicability={task.domain},
                )
                entries.append(entry)

        return entries

    def _extract_domain_heuristics(self, task: TaskSummary) -> List[KnowledgeEntry]:
        """Extract domain-specific heuristics."""
        entries = []

        # Domain-specific patterns
        domain_patterns = {
            "software_development": self._extract_dev_heuristics,
            "data_science": self._extract_ds_heuristics,
            "quantitative_trading": self._extract_trading_heuristics,
            "web_development": self._extract_web_heuristics,
        }

        extractor = domain_patterns.get(task.domain)
        if extractor:
            heuristics = extractor(task)
            for heuristic in heuristics:
                knowledge_id = self._generate_knowledge_id(
                    "domain_heuristic", f"{task.domain}_{heuristic['type']}"
                )

                entry = KnowledgeEntry(
                    knowledge_id=knowledge_id,
                    knowledge_type=KnowledgeType.DOMAIN_HEURISTIC,
                    content=heuristic,
                    context_tags=self._generate_context_tags(task, [task.domain]),
                    success_metrics={
                        "applicability_score": heuristic.get("confidence", 0.7)
                    },
                    confidence_score=heuristic.get("confidence", 0.7),
                    source_tasks={task.task_id},
                    domain_applicability={task.domain},
                )
                entries.append(entry)

        return entries

    def _extract_tool_preferences(self, task: TaskSummary) -> List[KnowledgeEntry]:
        """Extract tool and library preferences."""
        entries = []

        if task.final_status == "success" and task.tools_used:
            # Group tools by category
            tool_categories = self._categorize_tools(task.tools_used)

            for category, tools in tool_categories.items():
                preference = {
                    "category": category,
                    "preferred_tools": list(tools),
                    "context": {
                        "domain": task.domain,
                        "task_type": self._categorize_task(task.description),
                        "success_metrics": task.performance_metrics,
                    },
                    "reasoning": self._infer_tool_reasoning(tools, task),
                }

                knowledge_id = self._generate_knowledge_id(
                    "tool_preference", f"{task.domain}_{category}"
                )

                entry = KnowledgeEntry(
                    knowledge_id=knowledge_id,
                    knowledge_type=KnowledgeType.TOOL_PREFERENCE,
                    content=preference,
                    context_tags=self._generate_context_tags(task, list(tools)),
                    success_metrics={"preference_strength": 0.8},
                    confidence_score=0.8,
                    source_tasks={task.task_id},
                    domain_applicability={task.domain},
                )
                entries.append(entry)

        return entries

    def _extract_error_resolutions(self, task: TaskSummary) -> List[KnowledgeEntry]:
        """Extract error → solution mappings."""
        entries = []

        for error in task.errors_encountered:
            for solution in task.solutions_applied:
                if error.get("timestamp", 0) < solution.get(
                    "timestamp", 0
                ) and solution.get("success", False):

                    resolution = {
                        "error_pattern": {
                            "type": error.get("error_type"),
                            "stage": error.get("stage"),
                            "signature": self._extract_error_signature(
                                error.get("message", "")
                            ),
                        },
                        "solution": {
                            "approach": solution.get("approach"),
                            "commands": solution.get("commands", []),
                            "reasoning": solution.get("reasoning", ""),
                        },
                        "effectiveness": solution.get("effectiveness", 0.8),
                        "context": {
                            "domain": task.domain,
                            "tools_available": list(task.tools_used),
                        },
                    }

                    knowledge_id = self._generate_knowledge_id(
                        "error_resolution",
                        f"{resolution['error_pattern']['type']}_{resolution['solution']['approach']}",
                    )

                    entry = KnowledgeEntry(
                        knowledge_id=knowledge_id,
                        knowledge_type=KnowledgeType.ERROR_RESOLUTION,
                        content=resolution,
                        context_tags=self._generate_context_tags(
                            task, [resolution["error_pattern"]["type"]]
                        ),
                        success_metrics={
                            "resolution_success_rate": solution.get(
                                "effectiveness", 0.8
                            )
                        },
                        confidence_score=solution.get("effectiveness", 0.8),
                        source_tasks={task.task_id},
                        domain_applicability={task.domain},
                    )
                    entries.append(entry)

        return entries

    def _extract_optimization_rules(self, task: TaskSummary) -> List[KnowledgeEntry]:
        """Extract performance optimization patterns."""
        entries = []

        # Look for performance improvements
        if task.performance_metrics.get("improvement_factor", 1.0) > 1.2:
            optimization = {
                "optimization_type": "performance_improvement",
                "techniques_used": self._identify_optimization_techniques(task),
                "improvement_metrics": {
                    "factor": task.performance_metrics.get("improvement_factor", 1.0),
                    "baseline": task.performance_metrics.get(
                        "baseline_performance", {}
                    ),
                    "optimized": task.performance_metrics.get("final_performance", {}),
                },
                "context": {
                    "domain": task.domain,
                    "problem_size": task.metadata.get("problem_size", "medium"),
                },
            }

            knowledge_id = self._generate_knowledge_id(
                "optimization_rule", f"{task.domain}_performance"
            )

            entry = KnowledgeEntry(
                knowledge_id=knowledge_id,
                knowledge_type=KnowledgeType.OPTIMIZATION_RULE,
                content=optimization,
                context_tags=self._generate_context_tags(
                    task, ["optimization", "performance"]
                ),
                success_metrics={
                    "improvement_factor": optimization["improvement_metrics"]["factor"]
                },
                confidence_score=0.8,
                source_tasks={task.task_id},
                domain_applicability={task.domain},
            )
            entries.append(entry)

        return entries

    def _extract_quality_gates(self, task: TaskSummary) -> List[KnowledgeEntry]:
        """Extract quality requirements and gates."""
        entries = []

        if task.final_status == "success" and task.quality_metrics:
            quality_gate = {
                "domain": task.domain,
                "minimum_requirements": {},
                "recommended_targets": {},
                "validation_methods": [],
            }

            # Extract quality thresholds that led to success
            for metric, value in task.quality_metrics.items():
                if value > 0.7:  # Only include high-quality metrics
                    quality_gate["minimum_requirements"][metric] = (
                        value * 0.8
                    )  # 80% of achieved
                    quality_gate["recommended_targets"][metric] = value

            # Add validation methods used
            quality_gate["validation_methods"] = task.metadata.get(
                "validation_methods", []
            )

            knowledge_id = self._generate_knowledge_id(
                "quality_gate", f"{task.domain}_standards"
            )

            entry = KnowledgeEntry(
                knowledge_id=knowledge_id,
                knowledge_type=KnowledgeType.QUALITY_GATE,
                content=quality_gate,
                context_tags=self._generate_context_tags(
                    task, ["quality", task.domain]
                ),
                success_metrics={
                    "quality_score": statistics.mean(task.quality_metrics.values())
                },
                confidence_score=0.8,
                source_tasks={task.task_id},
                domain_applicability={task.domain},
            )
            entries.append(entry)

        return entries

    # Helper methods for extraction
    def _generate_knowledge_id(
        self, knowledge_type: str, content_signature: str
    ) -> str:
        """Generate unique knowledge ID."""
        signature = f"{knowledge_type}_{content_signature}"
        return hashlib.md5(signature.encode()).hexdigest()[:16]

    def _generate_context_tags(
        self, task: TaskSummary, additional_tags: List[str]
    ) -> Set[str]:
        """Generate context tags for knowledge entry."""
        tags = {
            task.domain,
            self._categorize_task(task.description),
            f"complexity_{self._estimate_complexity(task)}",
        }
        tags.update(additional_tags)
        tags.update(task.tools_used)
        return tags

    def _categorize_task(self, description: str) -> str:
        """Categorize task type from description."""
        desc_lower = description.lower()

        categories = {
            "api_development": ["api", "endpoint", "rest", "graphql"],
            "data_processing": ["data", "csv", "process", "analysis"],
            "web_development": ["website", "frontend", "backend", "web"],
            "testing": ["test", "unit test", "integration"],
            "deployment": ["deploy", "production", "docker", "kubernetes"],
            "optimization": ["optimize", "performance", "speed", "efficiency"],
            "bug_fix": ["fix", "bug", "error", "issue"],
            "feature_development": ["add", "implement", "create", "develop"],
        }

        for category, keywords in categories.items():
            if any(keyword in desc_lower for keyword in keywords):
                return category

        return "general_development"

    def _estimate_complexity(self, task: TaskSummary) -> str:
        """Estimate task complexity."""
        indicators = {
            "simple": task.duration < 300,  # 5 minutes
            "medium": task.duration < 1800,  # 30 minutes
            "complex": task.duration < 7200,  # 2 hours
        }

        for complexity, condition in indicators.items():
            if condition:
                return complexity

        return "very_complex"

    def _calculate_efficiency(self, task: TaskSummary) -> float:
        """Calculate efficiency score for the task."""  # Based on cost, time, and rework
        base_score = 1.0

        # Penalize for high cost
        if (
            task.cost_metrics.get("total_cost", 0)
            > task.cost_metrics.get("budget", 1) * 0.8
        ):
            base_score *= 0.8

        # Penalize for many retries
        retry_count = sum(1 for s in task.strategies_used if s.get("action") == "RETRY")
        if retry_count > 3:
            base_score *= 0.7

        # Bonus for fast completion
        if task.duration < 600:  # 10 minutes
            base_score *= 1.2

        return min(1.0, base_score)

    def _calculate_pattern_confidence(
        self, task: TaskSummary, pattern: List[str]
    ) -> float:
        """Calculate confidence in a strategy pattern."""
        base_confidence = 0.7

        # Bonus for successful completion
        if task.final_status == "success":
            base_confidence += 0.2

        # Bonus for efficiency
        efficiency = self._calculate_efficiency(task)
        base_confidence += efficiency * 0.1

        # Penalty for rare patterns
        if len(pattern) > 4:
            base_confidence -= 0.1

        return min(0.95, max(0.3, base_confidence))

    def _extract_template_from_artifact(
        self, artifact: str, task: TaskSummary
    ) -> Optional[Dict[str, Any]]:
        """Extract solution template from artifact."""  # Simplified template extraction
        if len(artifact) < 50:
            return None

        template_type = self._identify_template_type(artifact)
        if not template_type:
            return None

        return {
            "template_type": template_type,
            "pattern": self._extract_code_pattern(artifact),
            "reusability_score": self._calculate_reusability(artifact),
            "domain": task.domain,
            "context_requirements": self._extract_requirements(artifact),
        }

    def _identify_template_type(self, artifact: str) -> Optional[str]:
        """Identify the type of solution template."""
        patterns = {
            "rest_api": ["@app.route", "FastAPI", "flask", "def api_"],
            "data_processor": ["pandas", "numpy", "def process_", "DataFrame"],
            "test_suite": ["def test_", "pytest", "unittest", "assert"],
            "class_definition": ["class ", "__init__", "self."],
            "configuration": ["config", "settings", "ENV"],
        }

        artifact_lower = artifact.lower()
        for template_type, keywords in patterns.items():
            if any(keyword.lower() in artifact_lower for keyword in keywords):
                return template_type

        return None

    def _extract_code_pattern(self, artifact: str) -> str:
        """Extract reusable pattern from code."""  # Simplified pattern extraction
        lines = artifact.split("\n")
        important_lines = [
            line
            for line in lines
            if any(
                keyword in line.lower()
                for keyword in ["def ", "class ", "import ", "@"]
            )
        ]
        return "\n".join(important_lines[:10])  # First 10 important lines

    def _calculate_reusability(self, artifact: str) -> float:
        """Calculate how reusable an artifact is."""
        base_score = 0.5

        # Bonus for functions/classes
        if "def " in artifact or "class " in artifact:
            base_score += 0.2

        # Bonus for documentation
        if '"""' in artifact or "'''" in artifact:
            base_score += 0.1

        # Bonus for parameterization
        if "def " in artifact and "(" in artifact:
            base_score += 0.1

        # Penalty for hardcoded values
        if any(
            hardcode in artifact for hardcode in ["localhost", "127.0.0.1", "/tmp/"]
        ):
            base_score -= 0.1

        return min(1.0, max(0.2, base_score))

    def _extract_requirements(self, artifact: str) -> List[str]:
        """Extract requirements from artifact."""
        requirements = []

        # Extract imports
        import_lines = [
            line.strip()
            for line in artifact.split("\n")
            if line.strip().startswith("import ")
        ]
        requirements.extend(import_lines)

        # Extract from comments
        comment_lines = [
            line.strip()
            for line in artifact.split("\n")
            if line.strip().startswith("#")
        ]
        requirements.extend(comment_lines[:3])  # First 3 comments

        return requirements

    def _extract_error_signature(self, error_message: str) -> str:
        """Extract reusable signature from error message."""  # Remove specific details to create reusable pattern
        signature = error_message

        # Remove file paths
        signature = re.sub(r"/[^\s]+/", "/{path}/", signature)

        # Remove line numbers
        signature = re.sub(r"line \d+", "line {N}", signature)

        # Remove specific values
        signature = re.sub(r"'[^']*'", "'{value}'", signature)

        return signature[:200]  # Limit length

    # Domain-specific heuristic extractors
    def _extract_dev_heuristics(self, task: TaskSummary) -> List[Dict[str, Any]]:
        """Extract software development heuristics."""
        heuristics = []

        if task.quality_metrics.get("test_coverage", 0) > 0.8:
            heuristics.append(
                {
                    "type": "testing_standard",
                    "content": f"Maintain test coverage above {task.quality_metrics['test_coverage']:.0%}",
                    "confidence": 0.8,
                }
            )

        if "git" in task.tools_used:
            heuristics.append(
                {
                    "type": "version_control",
                    "content": "Use git for version control in all projects",
                    "confidence": 0.9,
                }
            )

        return heuristics

    def _extract_ds_heuristics(self, task: TaskSummary) -> List[Dict[str, Any]]:
        """Extract data science heuristics."""
        heuristics = []

        if "pandas" in task.tools_used and "numpy" in task.tools_used:
            heuristics.append(
                {
                    "type": "data_processing_stack",
                    "content": "Use pandas + numpy for data processing tasks",
                    "confidence": 0.8,
                }
            )

        return heuristics

    def _extract_trading_heuristics(self, task: TaskSummary) -> List[Dict[str, Any]]:
        """Extract quantitative trading heuristics."""
        heuristics = []

        if task.quality_metrics.get("sharpe_ratio", 0) > 1.5:
            heuristics.append(
                {
                    "type": "risk_management",
                    "content": f"Target Sharpe ratio above {task.quality_metrics['sharpe_ratio']:.1f}",
                    "confidence": 0.9,
                }
            )

        return heuristics

    def _extract_web_heuristics(self, task: TaskSummary) -> List[Dict[str, Any]]:
        """Extract web development heuristics."""
        heuristics = []

        if task.performance_metrics.get("page_load_time", 0) < 2.0:
            heuristics.append(
                {
                    "type": "performance_standard",
                    "content": "Keep page load times under 2 seconds",
                    "confidence": 0.8,
                }
            )

        return heuristics

    def _categorize_tools(self, tools: Set[str]) -> Dict[str, Set[str]]:
        """Categorize tools by function."""
        categories = defaultdict(set)

        tool_mappings = {
            "testing": {"pytest", "unittest", "nose", "jest"},
            "web_framework": {"flask", "django", "fastapi", "express"},
            "data_processing": {"pandas", "numpy", "scipy", "dask"},
            "database": {"sqlite3", "postgresql", "mongodb", "redis"},
            "deployment": {"docker", "kubernetes", "aws", "heroku"},
            "version_control": {"git", "svn", "mercurial"},
        }

        for tool in tools:
            tool_lower = tool.lower()
            for category, category_tools in tool_mappings.items():
                if any(ct in tool_lower for ct in category_tools):
                    categories[category].add(tool)
                    break
            else:
                categories["other"].add(tool)

        return dict(categories)

    def _infer_tool_reasoning(self, tools: Set[str], task: TaskSummary) -> str:
        """Infer reasoning for tool preference."""
        if task.performance_metrics.get("efficiency_score", 0) > 0.8:
            return "High efficiency and performance in this context"
        elif task.quality_metrics.get("overall_score", 0) > 0.8:
            return "Excellent quality outcomes achieved"
        else:
            return "Successful completion with these tools"

    def _identify_optimization_techniques(self, task: TaskSummary) -> List[str]:
        """Identify optimization techniques used."""
        techniques = []

        # Look in lessons learned and metadata
        lessons = " ".join(task.lessons_learned).lower()

        technique_keywords = {
            "caching": ["cache", "cached", "caching"],
            "vectorization": ["vector", "numpy", "vectorize"],
            "parallel_processing": ["parallel", "multiprocess", "concurrent"],
            "algorithm_optimization": ["algorithm", "complexity", "optimize"],
            "database_indexing": ["index", "query optimization"],
            "lazy_loading": ["lazy", "on-demand"],
        }

        for technique, keywords in technique_keywords.items():
            if any(keyword in lessons for keyword in keywords):
                techniques.append(technique)

        return techniques


class KnowledgeRetriever:
    """
    Retrieves relevant knowledge for current tasks.
    """

    def __init__(self, knowledge_database: sqlite3.Connection):
        """Initialize knowledge retriever."""
        self.db = knowledge_database
        self.text_vectorizer = TfidfVectorizer(max_features=500, stop_words="english")
        self._build_knowledge_graph()

    def _build_knowledge_graph(self):
        """Build graph of knowledge relationships."""
        self.knowledge_graph = nx.DiGraph()

        # Add nodes and edges based on knowledge relationships
        cursor = self.db.execute(
            "SELECT knowledge_id, content, context_tags FROM knowledge_entries"
        )
        for row in cursor.fetchall():
            knowledge_id, content_json, tags_json = row
            self.knowledge_graph.add_node(
                knowledge_id,
                content=json.loads(content_json),
                tags=set(json.loads(tags_json)),
            )

    def retrieve_relevant_knowledge(
        self,
        current_context: Dict[str, Any],
        knowledge_types: Optional[List[KnowledgeType]] = None,
        max_results: int = 10,
    ) -> List[KnowledgeEntry]:
        """
        Retrieve knowledge relevant to current context.

        Args:
            current_context: Current task/decision context
            knowledge_types: Types of knowledge to retrieve
            max_results: Maximum number of results

        Returns:
            List of relevant knowledge entries, ranked by relevance
        """  # Build query conditions
        conditions = []
        params = []

        if knowledge_types:
            type_names = [kt.name for kt in knowledge_types]
            conditions.append(
                f"knowledge_type IN ({','.join(['?' for _ in type_names])})"
            )
            params.extend(type_names)

        # Query database
        query = f"""
            SELECT * FROM knowledge_entries 
            {f"WHERE {' AND '.join(conditions)}" if conditions else ""}
            ORDER BY confidence_score DESC, usage_count DESC
            LIMIT ?
        """
        params.append(max_results * 3)  # Get more for filtering

        cursor = self.db.execute(query, params)

        # Convert to KnowledgeEntry objects
        entries = []
        for row in cursor.fetchall():
            entry = self._row_to_knowledge_entry(row)
            entries.append(entry)

        # Calculate relevance scores
        scored_entries = []
        for entry in entries:
            relevance = self._calculate_relevance(entry, current_context)
            if relevance > 0.3:  # Minimum relevance threshold
                scored_entries.append((entry, relevance))

        # Sort by relevance and return top results
        scored_entries.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored_entries[:max_results]]

    def _calculate_relevance(
        self, entry: KnowledgeEntry, context: Dict[str, Any]
    ) -> float:
        """Calculate relevance score between knowledge entry and current context."""
        relevance = 0.0

        # Domain match
        current_domain = context.get("domain", "")
        if current_domain in entry.domain_applicability:
            relevance += 0.3

        # Context tag overlap
        current_tags = self._extract_context_tags(context)
        tag_overlap = len(entry.context_tags & current_tags) / max(
            len(entry.context_tags), 1
        )
        relevance += tag_overlap * 0.3

        # Stage match (for strategy patterns)
        current_stage = context.get("stage", "")
        if entry.knowledge_type == KnowledgeType.STRATEGY_PATTERN:
            if (
                "stage_context" in entry.content
                and current_stage in entry.content["stage_context"]
            ):
                relevance += 0.2

        # Error type match (for error resolutions)
        if entry.knowledge_type == KnowledgeType.ERROR_RESOLUTION:
            current_error = context.get("error", "")
            entry_error_type = entry.content.get("error_pattern", {}).get("type", "")
            if entry_error_type and entry_error_type in current_error.lower():
                relevance += 0.4

        # Recency boost (prefer recent successful knowledge)
        if entry.last_success:
            days_old = (datetime.now() - entry.last_success).days
            recency_factor = max(0, 1 - days_old / 90)  # Decay over 90 days
            relevance += recency_factor * 0.1

        # Usage count boost (prefer proven knowledge)
        usage_factor = min(entry.usage_count / 10, 1.0)  # Max boost at 10 uses
        relevance += usage_factor * 0.1

        # Confidence factor
        relevance *= entry.confidence_score

        return min(1.0, relevance)

    def _extract_context_tags(self, context: Dict[str, Any]) -> Set[str]:
        """Extract tags from current context."""
        tags = set()

        # Add domain
        if "domain" in context:
            tags.add(context["domain"])

        # Add stage
        if "stage" in context:
            tags.add(context["stage"])

        # Add error type
        if "error" in context:
            error_type = self._categorize_error(context["error"])
            if error_type:
                tags.add(error_type)

        # Add task type (inferred from description)
        if "task" in context:
            task_type = self._categorize_task_type(context["task"])
            tags.add(task_type)

        return tags

    def _categorize_error(self, error_message: str) -> Optional[str]:
        """Categorize error type from message."""
        error_lower = error_message.lower()

        error_types = {
            "module": ["modulenotfounderror", "import"],
            "permission": ["permission", "access denied"],
            "syntax": ["syntaxerror", "syntax"],
            "type": ["typeerror"],
            "value": ["valueerror"],
            "connection": ["connection", "timeout"],
            "validation": ["assertion", "validation"],
        }

        for error_type, keywords in error_types.items():
            if any(keyword in error_lower for keyword in keywords):
                return error_type

        return None

    def _categorize_task_type(self, task_description: str) -> str:
        """Categorize task type from description."""
        desc_lower = task_description.lower()

        if any(word in desc_lower for word in ["api", "endpoint", "rest"]):
            return "api_development"
        elif any(word in desc_lower for word in ["data", "analysis", "csv"]):
            return "data_processing"
        elif any(word in desc_lower for word in ["test", "testing"]):
            return "testing"
        elif any(word in desc_lower for word in ["fix", "bug", "error"]):
            return "bug_fix"
        else:
            return "general_development"

    def _row_to_knowledge_entry(self, row: Tuple) -> KnowledgeEntry:
        """Convert database row to KnowledgeEntry object."""
        (
            knowledge_id,
            knowledge_type_name,
            content_json,
            context_tags_json,
            success_metrics_json,
            confidence_score,
            usage_count,
            last_success_str,
            source_tasks_json,
            domain_applicability_json,
            prerequisites_json,
            metadata_json,
            created_at_str,
            updated_at_str,
        ) = row

        return KnowledgeEntry(
            knowledge_id=knowledge_id,
            knowledge_type=KnowledgeType[knowledge_type_name],
            content=json.loads(content_json),
            context_tags=set(json.loads(context_tags_json)),
            success_metrics=json.loads(success_metrics_json),
            confidence_score=confidence_score,
            usage_count=usage_count,
            last_success=(
                datetime.fromisoformat(last_success_str) if last_success_str else None
            ),
            source_tasks=set(json.loads(source_tasks_json)),
            domain_applicability=set(json.loads(domain_applicability_json)),
            prerequisites=json.loads(prerequisites_json),
            metadata=json.loads(metadata_json),
            created_at=datetime.fromisoformat(created_at_str),
            updated_at=datetime.fromisoformat(updated_at_str),
        )


class CrossTaskKnowledgeLedger:
    """
    Main knowledge ledger that orchestrates knowledge extraction, storage, and retrieval.
    """

    def __init__(self, persistence_path: Path):
        """
        Initialize cross-task knowledge ledger.

        Args:
            persistence_path: Path for storing knowledge database
        """
        self.persistence_path = persistence_path
        self.persistence_path.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.extractor = KnowledgeExtractor()
        self.database = self._init_database()
        self.retriever = KnowledgeRetriever(self.database)

        # Statistics
        self.stats = {
            "total_tasks_processed": 0,
            "total_knowledge_entries": 0,
            "knowledge_by_type": defaultdict(int),
            "knowledge_by_domain": defaultdict(int),
        }

        self._load_stats()

        logger.info(
            f"CrossTaskKnowledgeLedger initialized with {self.stats['total_knowledge_entries']} entries"
        )

    def _init_database(self) -> sqlite3.Connection:
        """Initialize SQLite database for knowledge storage."""
        db_path = self.persistence_path / "knowledge_ledger.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)

        # Create knowledge entries table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                knowledge_id TEXT PRIMARY KEY,
                knowledge_type TEXT NOT NULL,
                content TEXT NOT NULL,
                context_tags TEXT NOT NULL,
                success_metrics TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                usage_count INTEGER DEFAULT 0,
                last_success TEXT,
                source_tasks TEXT NOT NULL,
                domain_applicability TEXT NOT NULL,
                prerequisites TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        )

        # Create indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_knowledge_type ON knowledge_entries(knowledge_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_confidence ON knowledge_entries(confidence_score)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage ON knowledge_entries(usage_count)"
        )

        # Create task summaries table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_summaries (
                task_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                domain TEXT NOT NULL,
                final_status TEXT NOT NULL,
                stage_sequence TEXT NOT NULL,
                strategies_used TEXT NOT NULL,
                tools_used TEXT NOT NULL,
                errors_encountered TEXT NOT NULL,
                solutions_applied TEXT NOT NULL,
                quality_metrics TEXT NOT NULL,
                performance_metrics TEXT NOT NULL,
                cost_metrics TEXT NOT NULL,
                duration REAL NOT NULL,
                artifacts_produced TEXT NOT NULL,
                lessons_learned TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
        """
        )

        conn.commit()
        return conn

    def process_completed_task(self, task_summary: TaskSummary):
        """
        Process a completed task and extract knowledge.

        Args:
            task_summary: Summary of the completed task
        """
        logger.info(f"Processing completed task: {task_summary.task_id}")

        # Store task summary
        self._store_task_summary(task_summary)

        # Extract knowledge
        knowledge_entries = self.extractor.extract_knowledge(task_summary)

        # Store or update knowledge entries
        for entry in knowledge_entries:
            self._store_or_update_knowledge(entry)

        # Update statistics
        self.stats["total_tasks_processed"] += 1
        self._update_stats()

        logger.info(f"Extracted and stored {len(knowledge_entries)} knowledge entries")

    def get_relevant_knowledge(
        self,
        current_context: Dict[str, Any],
        knowledge_types: Optional[List[KnowledgeType]] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get knowledge relevant to current context.

        Args:
            current_context: Current task/decision context
            knowledge_types: Specific types of knowledge to retrieve
            max_results: Maximum number of results

        Returns:
            List of relevant knowledge with application guidance
        """  # Retrieve relevant entries
        entries = self.retriever.retrieve_relevant_knowledge(
            current_context, knowledge_types, max_results
        )

        # Format for consumption
        formatted_knowledge = []
        for entry in entries:
            formatted = {
                "type": entry.knowledge_type.name,
                "content": entry.content,
                "confidence": entry.confidence_score,
                "usage_count": entry.usage_count,
                "applicability": self._assess_applicability(entry, current_context),
                "application_guidance": self._generate_application_guidance(
                    entry, current_context
                ),
                "prerequisites_met": self._check_prerequisites(entry, current_context),
                "source_info": {
                    "source_tasks": list(entry.source_tasks),
                    "domains": list(entry.domain_applicability),
                    "created_at": entry.created_at.isoformat(),
                },
            }
            formatted_knowledge.append(formatted)

        # Update usage counts
        for entry in entries:
            self._increment_usage(entry.knowledge_id)

        return formatted_knowledge

    def record_knowledge_application(
        self,
        knowledge_id: str,
        success: bool,
        context: Dict[str, Any],
        outcome_metrics: Dict[str, float],
    ):
        """
        Record the outcome of applying knowledge.

        Args:
            knowledge_id: ID of applied knowledge
            success: Whether application was successful
            context: Context in which it was applied
            outcome_metrics: Metrics from the outcome
        """
        if success:
            # Update last success time
            self.database.execute(
                "UPDATE knowledge_entries SET last_success = ? WHERE knowledge_id = ?",
                (datetime.now().isoformat(), knowledge_id),
            )

            # Potentially update confidence score based on continued success
            self._update_confidence_based_on_outcome(knowledge_id, outcome_metrics)

        self.database.commit()

        logger.info(
            f"Recorded knowledge application: {knowledge_id} -> {'success' if success else 'failure'}"
        )

    def _store_task_summary(self, task: TaskSummary):
        """Store task summary in database."""
        self.database.execute(
            """
            INSERT OR REPLACE INTO task_summaries VALUES 
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task.task_id,
                task.description,
                task.domain,
                task.final_status,
                json.dumps(task.stage_sequence),
                json.dumps(task.strategies_used),
                json.dumps(list(task.tools_used)),
                json.dumps(task.errors_encountered),
                json.dumps(task.solutions_applied),
                json.dumps(task.quality_metrics),
                json.dumps(task.performance_metrics),
                json.dumps(task.cost_metrics),
                task.duration,
                json.dumps(task.artifacts_produced),
                json.dumps(task.lessons_learned),
                task.completed_at.isoformat(),
                json.dumps(task.metadata),
            ),
        )
        self.database.commit()

    def _store_or_update_knowledge(self, entry: KnowledgeEntry):
        """Store new knowledge or update existing."""  # Check if knowledge already exists
        cursor = self.database.execute(
            "SELECT usage_count, confidence_score FROM knowledge_entries WHERE knowledge_id = ?",
            (entry.knowledge_id,),
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing entry
            current_usage, current_confidence = existing

            # Merge confidence (weighted average)
            new_confidence = (
                current_confidence * current_usage + entry.confidence_score
            ) / (current_usage + 1)

            self.database.execute(
                """
                UPDATE knowledge_entries SET 
                    usage_count = usage_count + 1,
                    confidence_score = ?,
                    source_tasks = ?,
                    updated_at = ?
                WHERE knowledge_id = ?
            """,
                (
                    new_confidence,
                    json.dumps(
                        list(entry.source_tasks | {existing[0] for existing in []})
                    ),
                    datetime.now().isoformat(),
                    entry.knowledge_id,
                ),
            )
        else:
            # Insert new entry
            self.database.execute(
                """INSERT INTO knowledge_entries VALUES 
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.knowledge_id,
                    entry.knowledge_type.name,
                    json.dumps(entry.content),
                    json.dumps(list(entry.context_tags)),
                    json.dumps(entry.success_metrics),
                    entry.confidence_score,
                    entry.usage_count,
                    entry.last_success.isoformat() if entry.last_success else None,
                    json.dumps(list(entry.source_tasks)),
                    json.dumps(list(entry.domain_applicability)),
                    json.dumps(entry.prerequisites),
                    json.dumps(entry.metadata),
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                ),
            )

            # Update statistics
            self.stats["total_knowledge_entries"] += 1
            self.stats["knowledge_by_type"][entry.knowledge_type.name] += 1
            for domain in entry.domain_applicability:
                self.stats["knowledge_by_domain"][domain] += 1

        self.database.commit()

    def _assess_applicability(
        self, entry: KnowledgeEntry, context: Dict[str, Any]
    ) -> float:
        """Assess how applicable knowledge is to current context."""  # This is handled by the retriever's relevance calculation
        return self.retriever._calculate_relevance(entry, context)

    def _generate_application_guidance(
        self, entry: KnowledgeEntry, context: Dict[str, Any]
    ) -> str:
        """Generate guidance on how to apply this knowledge."""
        guidance_templates = {
            KnowledgeType.STRATEGY_PATTERN: "Apply this strategy sequence: {pattern}",
            KnowledgeType.SOLUTION_TEMPLATE: "Use this solution template for {template_type}",
            KnowledgeType.ANTI_PATTERN: "Avoid this pattern: {pattern_type}",
            KnowledgeType.ERROR_RESOLUTION: "For error '{error_type}', try: {solution}",
            KnowledgeType.TOOL_PREFERENCE: "Consider using {tools} for {category}",
            KnowledgeType.DOMAIN_HEURISTIC: "Follow this heuristic: {content}",
            KnowledgeType.OPTIMIZATION_RULE: "Apply optimization: {techniques}",
            KnowledgeType.QUALITY_GATE: "Ensure quality standards: {requirements}",
        }

        template = guidance_templates.get(
            entry.knowledge_type, "Apply this knowledge: {content}"
        )

        try:
            return template.format(**entry.content)
        except KeyError:
            return f"Apply this {entry.knowledge_type.name.lower().replace('_', ' ')}"

    def _check_prerequisites(
        self, entry: KnowledgeEntry, context: Dict[str, Any]
    ) -> bool:
        """Check if prerequisites for applying this knowledge are met."""
        if not entry.prerequisites:
            return True

        # Simple prerequisite checking
        for prereq in entry.prerequisites:
            if "tool:" in prereq:
                tool_name = prereq.replace("tool:", "")
                available_tools = context.get("available_tools", [])
                if tool_name not in available_tools:
                    return False
            elif "domain:" in prereq:
                required_domain = prereq.replace("domain:", "")
                if context.get("domain") != required_domain:
                    return False

        return True

    def _increment_usage(self, knowledge_id: str):
        """Increment usage count for knowledge entry."""
        self.database.execute(
            "UPDATE knowledge_entries SET usage_count = usage_count + 1 WHERE knowledge_id = ?",
            (knowledge_id,),
        )
        self.database.commit()

    def _update_confidence_based_on_outcome(
        self, knowledge_id: str, outcome_metrics: Dict[str, float]
    ):
        """Update knowledge confidence based on application outcome."""  # Get current confidence
        cursor = self.database.execute(
            "SELECT confidence_score, usage_count FROM knowledge_entries WHERE knowledge_id = ?",
            (knowledge_id,),
        )
        row = cursor.fetchone()

        if row:
            current_confidence, usage_count = row

            # Calculate success score from outcome metrics
            success_score = outcome_metrics.get("success_score", 0.8)

            # Update confidence using exponential moving average
            alpha = 1.0 / max(usage_count, 1)  # Decreasing learning rate
            new_confidence = (1 - alpha) * current_confidence + alpha * success_score

            self.database.execute(
                "UPDATE knowledge_entries SET confidence_score = ? WHERE knowledge_id = ?",
                (new_confidence, knowledge_id),
            )
            self.database.commit()

    def _load_stats(self):
        """Load statistics from database."""  # Count total entries
        cursor = self.database.execute("SELECT COUNT(*) FROM knowledge_entries")
        self.stats["total_knowledge_entries"] = cursor.fetchone()[0]

        # Count by type
        cursor = self.database.execute(
            "SELECT knowledge_type, COUNT(*) FROM knowledge_entries GROUP BY knowledge_type"
        )
        for knowledge_type, count in cursor.fetchall():
            self.stats["knowledge_by_type"][knowledge_type] = count

        # Count by domain
        cursor = self.database.execute(
            "SELECT domain_applicability FROM knowledge_entries"
        )
        for (domain_json,) in cursor.fetchall():
            domains = json.loads(domain_json)
            for domain in domains:
                self.stats["knowledge_by_domain"][domain] += 1

    def _update_stats(self):
        """Update internal statistics."""  # Reload stats from database
        self._load_stats()

    def get_knowledge_statistics(self) -> Dict[str, Any]:
        """Get comprehensive knowledge statistics."""
        return {
            "total_tasks_processed": self.stats["total_tasks_processed"],
            "total_knowledge_entries": self.stats["total_knowledge_entries"],
            "knowledge_by_type": dict(self.stats["knowledge_by_type"]),
            "knowledge_by_domain": dict(self.stats["knowledge_by_domain"]),
            "average_confidence": self._calculate_average_confidence(),
            "most_used_knowledge": self._get_most_used_knowledge(),
            "recent_knowledge": self._get_recent_knowledge(),
        }

    def _calculate_average_confidence(self) -> float:
        """Calculate average confidence across all knowledge."""
        cursor = self.database.execute(
            "SELECT AVG(confidence_score) FROM knowledge_entries"
        )
        result = cursor.fetchone()[0]
        return result if result else 0.0

    def _get_most_used_knowledge(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most frequently used knowledge."""
        cursor = self.database.execute(
            """
            SELECT knowledge_id, knowledge_type, usage_count, confidence_score 
            FROM knowledge_entries 
            ORDER BY usage_count DESC 
            LIMIT ?
        """,
            (limit,),
        )

        return [
            {
                "knowledge_id": row[0],
                "type": row[1],
                "usage_count": row[2],
                "confidence": row[3],
            }
            for row in cursor.fetchall()
        ]

    def _get_recent_knowledge(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recently created knowledge."""
        cutoff = datetime.now() - timedelta(days=days)

        cursor = self.database.execute(
            """
            SELECT knowledge_id, knowledge_type, created_at, confidence_score
            FROM knowledge_entries 
            WHERE created_at > ?
            ORDER BY created_at DESC
        """,
            (cutoff.isoformat(),),
        )

        return [
            {
                "knowledge_id": row[0],
                "type": row[1],
                "created_at": row[2],
                "confidence": row[3],
            }
            for row in cursor.fetchall()
        ]

    def cleanup_old_knowledge(self, days_to_keep: int = 365):
        """Clean up old, unused knowledge."""
        cutoff = datetime.now() - timedelta(days=days_to_keep)

        # Delete knowledge with low usage and old age
        cursor = self.database.execute(
            """
            DELETE FROM knowledge_entries 
            WHERE usage_count = 0 AND created_at < ?
        """,
            (cutoff.isoformat(),),
        )

        deleted_count = cursor.rowcount
        self.database.commit()

        # Update statistics
        self._update_stats()

        logger.info(f"Cleaned up {deleted_count} old knowledge entries")
        return deleted_count


# Example usage and testing
if __name__ == "__main__":
    import tempfile

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = CrossTaskKnowledgeLedger(Path(temp_dir))

        # Create sample task summary
        task_summary = TaskSummary(
            task_id="test_task_001",
            description="Create REST API for user authentication with JWT tokens",
            domain="software_development",
            final_status="success",
            stage_sequence=[
                "think",
                "research",
                "decide",
                "execute",
                "validate",
                "solidify",
            ],
            strategies_used=[
                {"action": "PROCEED", "stage": "think"},
                {"action": "FETCH_INFO", "stage": "research"},
                {"action": "PROCEED", "stage": "decide"},
                {"action": "RETRY", "stage": "execute"},
                {"action": "PROCEED", "stage": "validate"},
            ],
            tools_used={"fastapi", "jwt", "bcrypt", "pytest"},
            errors_encountered=[
                {
                    "stage": "execute",
                    "error_type": "ModuleNotFoundError",
                    "message": "ModuleNotFoundError: No module named 'bcrypt'",
                    "resolution_attempts": 1,
                    "timestamp": 1000,
                }
            ],
            solutions_applied=[
                {
                    "approach": "install_dependency",
                    "commands": ["pip install bcrypt"],
                    "success": True,
                    "effectiveness": 0.9,
                    "timestamp": 1100,
                }
            ],
            quality_metrics={
                "test_coverage": 0.85,
                "code_quality": 0.9,
                "overall_score": 0.87,
            },
            performance_metrics={"efficiency_score": 0.8, "time_to_completion": 1200},
            cost_metrics={"total_cost": 0.75, "budget": 2.0},
            duration=1200,
            artifacts_produced=[
                """from fastapi import FastAPI, HTTPException
import bcrypt
import jwt

app = FastAPI()

@app.post("/register")
def register(user_data):
    hashed = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt())
    return {"message": "User created"}

@app.post("/login") 
def login(credentials):
    if validate_user(credentials):
        token = jwt.encode({"user_id": user.id}, "secret")
        return {"token": token}
    raise HTTPException(401, "Invalid credentials")
"""
            ],
            lessons_learned=[
                "FastAPI works well for REST APIs",
                "bcrypt is good for password hashing",
                "JWT tokens provide stateless authentication",
            ],
        )

        print("=== CROSS-TASK KNOWLEDGE LEDGER TESTING ===\n")

        # Process the task
        ledger.process_completed_task(task_summary)

        # Get statistics
        print("Knowledge Statistics:")
        stats = ledger.get_knowledge_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")

        print("\n" + "=" * 50)

        # Test knowledge retrieval
        current_context = {
            "domain": "software_development",
            "stage": "execute",
            "error": "ModuleNotFoundError: No module named 'requests'",
            "task": "Create REST API for data processing",
        }

        print(f"\nRetrieving knowledge for context: {current_context}")

        relevant_knowledge = ledger.get_relevant_knowledge(
            current_context, max_results=3
        )

        print(f"\nFound {len(relevant_knowledge)} relevant knowledge entries:")
        for i, knowledge in enumerate(relevant_knowledge, 1):
            print(f"\n{i}. {knowledge['type']}")
            print(f"   Confidence: {knowledge['confidence']:.2f}")
            print(f"   Application: {knowledge['application_guidance']}")
            print(f"   Prerequisites met: {knowledge['prerequisites_met']}")
            print(f"   Usage count: {knowledge['usage_count']}")
            print(f"   Source: {knowledge['source_info']['domains']}")

        # Test knowledge application recording
        if relevant_knowledge:
            first_knowledge = relevant_knowledge[0]
            knowledge_id = first_knowledge["content"].get(
                "knowledge_id", "test_knowledge"
            )

            ledger.record_knowledge_application(
                knowledge_id="strategy_pattern_"
                + hashlib.md5(b"PROCEED_FETCH_INFO_PROCEED").hexdigest()[:16],
                success=True,
                context=current_context,
                outcome_metrics={"success_score": 0.9, "efficiency": 0.8},
            )
            print(f"\nRecorded successful application of knowledge")

        print("\n=== KNOWLEDGE LEDGER TESTING COMPLETE ===")
