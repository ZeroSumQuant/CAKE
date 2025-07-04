#!/usr/bin/env python3
"""stage_router.py - Dynamic Stage Navigation for CAKE

Provides intelligent routing through TRRDEVS stages with support for
backtracking, skipping, and dynamic reordering based on strategic decisions.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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
                    "edges": lambda self: [],
                    "successors": lambda self, node: [],
                    "predecessors": lambda self, node: [],
                    "has_node": lambda self, node: True,
                    "has_edge": lambda self, u, v: False,
                    "get_edge_data": lambda self, u, v: {},
                    "degree": lambda self, node: 0,
                    "in_degree": lambda self, node: 0,
                    "out_degree": lambda self, node: 0,
                },
            )()


from enum import Enum

from cake.core.strategist import Decision, StrategyDecision

# Configure module logger
logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """Status of each stage in the workflow."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageTransition:
    """
    Records a stage transition for analysis.

    Attributes:
        from_stage: Origin stage
        to_stage: Destination stage
        timestamp: When transition occurred
        reason: Why this transition happened
        decision: Strategic decision that caused it
    """

    from_stage: str
    to_stage: Optional[str]
    timestamp: datetime
    reason: str
    decision: StrategyDecision
    metadata: Dict[str, any] = field(default_factory=dict)


class StageRouter:
    """
    Intelligent stage router that manages TRRDEVS workflow navigation.

    Features:
    - Dynamic stage graph with allowed transitions
    - Backtracking support for error recovery
    - Skip patterns for optimization
    - Transition history and analytics
    - Path finding for optimal completion
    """

    # Standard TRRDEVS stages
    STANDARD_STAGES = [
        "think",  # Understand the problem
        "research",  # Research solutions
        "reflect",  # Reflect on approaches
        "decide",  # Decide on approach
        "execute",  # Execute the plan
        "validate",  # Validate results
        "solidify",  # Solidify and document
    ]

    def __init__(
        self,
        stages: Optional[List[str]] = None,
        custom_transitions: Optional[Dict[Tuple[str, str], Dict]] = None,
    ):
        """
        Initialize router with stages and transition rules.

        Args:
            stages: List of stage names (defaults to STANDARD_STAGES)
            custom_transitions: Additional allowed transitions beyond defaults
        """
        self.stages = stages or self.STANDARD_STAGES.copy()
        self.graph = self._build_stage_graph(custom_transitions)
        self.history: List[StageTransition] = []
        self.stage_status: Dict[str, StageStatus] = {
            stage: StageStatus.NOT_STARTED for stage in self.stages
        }
        self.current_stage: Optional[str] = None

        # Performance tracking
        self.stage_timings: Dict[str, List[float]] = {
            stage: [] for stage in self.stages
        }
        self.transition_counts: Dict[Tuple[str, str], int] = {}

        logger.info(f"StageRouter initialized with {len(self.stages)} stages")

    def _build_stage_graph(
        self, custom_transitions: Optional[Dict] = None
    ) -> nx.DiGraph:
        """
        Build directed graph of valid stage transitions.

        Creates both forward progression and strategic backward edges.
        """
        G = nx.DiGraph()

        # Add all stages as nodes with metadata
        for i, stage in enumerate(self.stages):
            G.add_node(stage, index=i, status=StageStatus.NOT_STARTED)

        # Add standard forward progression
        for i in range(len(self.stages) - 1):
            G.add_edge(
                self.stages[i],
                self.stages[i + 1],
                weight=1.0,
                transition_type="forward",
            )

        # Add strategic backward edges (error recovery patterns)
        backward_edges = [
            # Failed validation often means bad implementation
            ("validate", "execute", {"weight": 2.0, "reason": "Validation failure"}),
            (
                "validate",
                "reflect",
                {"weight": 3.0, "reason": "Design reconsideration"},
            ),
            # Failed execution might need replanning
            ("execute", "decide", {"weight": 2.0, "reason": "Execution failure"}),
            ("execute", "research", {"weight": 4.0, "reason": "Missing knowledge"}),
            # Bad reflection needs more research
            ("reflect", "research", {"weight": 2.0, "reason": "Insufficient research"}),
            # Bad decision needs reflection
            ("decide", "reflect", {"weight": 2.0, "reason": "Decision revision"}),
            # Can solidify from validate if all good
            ("validate", "solidify", {"weight": 0.5, "reason": "Fast track"}),
        ]

        for from_stage, to_stage, attrs in backward_edges:
            if from_stage in self.stages and to_stage in self.stages:
                G.add_edge(from_stage, to_stage, transition_type="backward", **attrs)

        # Add any custom transitions
        if custom_transitions:
            for (from_stage, to_stage), attrs in custom_transitions.items():
                if from_stage in self.stages and to_stage in self.stages:
                    G.add_edge(from_stage, to_stage, transition_type="custom", **attrs)

        return G

    def set_current_stage(self, stage: str) -> None:
        """Set the current stage and update status."""
        if stage not in self.stages:
            raise ValueError(f"Invalid stage: {stage}")

        # Mark previous stage as completed
        if self.current_stage:
            self.stage_status[self.current_stage] = StageStatus.COMPLETED

        self.current_stage = stage
        self.stage_status[stage] = StageStatus.IN_PROGRESS

    def next_stage(self, current: str, decision: StrategyDecision) -> Optional[str]:
        """
        Determine next stage based on strategic decision.

        Args:
            current: Current stage name
            decision: Strategic decision from Strategist

        Returns:
            Next stage name or None if workflow complete/aborted
        """  # Validate current stage
        if current not in self.stages:
            raise ValueError(f"Invalid current stage: {current}")

        # Record transition start time
        transition_start = datetime.now()

        # Determine next stage based on decision
        next_stage = None
        reason = decision.reason

        if decision.action == Decision.PROCEED:
            next_stage = self._get_next_forward_stage(current)
            reason = reason or "Normal progression"

        elif decision.action == Decision.REROUTE:
            if decision.target_stage and decision.target_stage in self.stages:
                next_stage = decision.target_stage
                reason = reason or f"Strategic reroute to {decision.target_stage}"
            else:
                logger.error(f"Invalid reroute target: {decision.target_stage}")
                next_stage = None

        elif decision.action == Decision.RETRY:
            next_stage = current
            reason = reason or "Retrying current stage"

        elif decision.action in [Decision.ABORT, Decision.ESCALATE]:
            next_stage = None
            reason = reason or f"Workflow {decision.action.name.lower()}"

        elif decision.action == Decision.PAUSE:
            next_stage = current  # Stay on current, but paused
            reason = reason or "Temporary pause"

        else:
            # For other decisions (FETCH_INFO, CREATE_RULE), stay on current
            next_stage = current
            reason = reason or f"Handling {decision.action.name}"

        # Validate transition is allowed
        if next_stage and current != next_stage:
            if not self._is_valid_transition(current, next_stage):
                logger.warning(
                    f"Invalid transition {current} -> {next_stage}, finding alternative"
                )
                next_stage = self._find_alternative_route(current, next_stage)

        # Record transition
        transition = StageTransition(
            from_stage=current,
            to_stage=next_stage,
            timestamp=transition_start,
            reason=reason,
            decision=decision,
        )
        self.history.append(transition)

        # Update transition counts
        if next_stage:
            key = (current, next_stage)
            self.transition_counts[key] = self.transition_counts.get(key, 0) + 1

        # Update current stage
        if next_stage and next_stage != current:
            self.set_current_stage(next_stage)

        logger.info(f"Stage transition: {current} -> {next_stage or 'END'} ({reason})")

        return next_stage

    def _get_next_forward_stage(self, current: str) -> Optional[str]:
        """Get the next stage in forward progression."""
        try:
            idx = self.stages.index(current)
            if idx + 1 < len(self.stages):
                return self.stages[idx + 1]
        except ValueError:
            pass
        return None

    def _is_valid_transition(self, from_stage: str, to_stage: str) -> bool:
        """Check if transition is allowed in the graph."""
        return self.graph.has_edge(from_stage, to_stage)

    def _find_alternative_route(self, from_stage: str, to_stage: str) -> Optional[str]:
        """Find alternative route when direct transition not allowed."""
        try:
            # Find shortest path
            path = nx.shortest_path(self.graph, from_stage, to_stage)
            if len(path) > 1:
                # Return first step in path
                return path[1]
        except nx.NetworkXNoPath:
            logger.warning(f"No path found from {from_stage} to {to_stage}")

        # Fallback to forward progression
        return self._get_next_forward_stage(from_stage)

    def get_remaining_stages(self, current: str) -> List[str]:
        """Get remaining stages to reach completion."""
        try:
            path = nx.shortest_path(self.graph, current, self.stages[-1])
            return path[1:]  # Exclude current
        except nx.NetworkXNoPath:
            return []

    def get_stage_status_summary(self) -> Dict[str, Dict[str, any]]:
        """Get comprehensive status of all stages."""
        summary = {}

        for stage in self.stages:
            summary[stage] = {
                "status": self.stage_status[stage].value,
                "visit_count": sum(1 for t in self.history if t.to_stage == stage),
                "average_time": (
                    sum(self.stage_timings[stage]) / len(self.stage_timings[stage])
                    if self.stage_timings[stage]
                    else 0
                ),
                "is_current": stage == self.current_stage,
            }

        return summary

    def can_skip_to(self, from_stage: str, to_stage: str) -> bool:
        """Check if we can skip directly to a stage."""
        if not self._is_valid_transition(from_stage, to_stage):
            return False

        # Check if intermediate stages are optional
        try:
            from_idx = self.stages.index(from_stage)
            to_idx = self.stages.index(to_stage)

            if to_idx <= from_idx:
                return True  # Backward movement always allowed if edge exists

            # Forward skip - check if all intermediate stages are completed or skippable
            for i in range(from_idx + 1, to_idx):
                status = self.stage_status[self.stages[i]]
                if status not in [StageStatus.COMPLETED, StageStatus.SKIPPED]:
                    return False

            return True

        except ValueError:
            return False

    def suggest_optimal_path(
        self, current: str, constraints: Dict[str, any] = None
    ) -> List[str]:
        """
        Suggest optimal path to completion given constraints.

        Args:
            current: Current stage
            constraints: Optional constraints like time_limit, must_visit_stages

        Returns:
            Ordered list of stages to visit
        """
        constraints = constraints or {}
        target = constraints.get("target", self.stages[-1])
        must_visit = set(constraints.get("must_visit", []))

        try:
            # Get base shortest path
            base_path = nx.shortest_path(self.graph, current, target, weight="weight")

            # Ensure must-visit stages are included
            if must_visit:
                # This is a simplified approach - in production use more sophisticated algorithms
                path = base_path
                for stage in must_visit:
                    if stage not in path and stage in self.stages:
                        # Find best insertion point
                        # (Simplified - just add before target)
                        path.insert(-1, stage)

                return path

            return base_path

        except nx.NetworkXNoPath:
            logger.error(f"No path from {current} to {target}")
            return []

    def get_transition_analysis(self) -> Dict[str, any]:
        """Analyze transition patterns for optimization."""
        if not self.history:
            return {}

        analysis = {
            "total_transitions": len(self.history),
            "unique_transitions": len(
                set((t.from_stage, t.to_stage) for t in self.history)
            ),
            "backward_transitions": sum(
                1
                for t in self.history
                if t.to_stage
                and self.stages.index(t.to_stage) < self.stages.index(t.from_stage)
            ),
            "retry_count": sum(1 for t in self.history if t.from_stage == t.to_stage),
            "most_common_transitions": self._get_most_common_transitions(),
            "average_path_length": self._calculate_average_path_length(),
            "bottleneck_stages": self._identify_bottlenecks(),
        }

        return analysis

    def _get_most_common_transitions(
        self, top_n: int = 5
    ) -> List[Tuple[Tuple[str, str], int]]:
        """Get most common transitions."""
        sorted_transitions = sorted(
            self.transition_counts.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_transitions[:top_n]

    def _calculate_average_path_length(self) -> float:
        """Calculate average path length to completion."""
        completed_paths = []
        current_path = []

        for transition in self.history:
            if transition.to_stage:
                current_path.append(transition.to_stage)
                if transition.to_stage == self.stages[-1]:
                    completed_paths.append(len(current_path))
                    current_path = []

        return sum(completed_paths) / len(completed_paths) if completed_paths else 0

    def _identify_bottlenecks(self) -> List[str]:
        """Identify stages that cause the most failures/retries."""
        failure_counts = {}

        for transition in self.history:
            if transition.decision.action in [Decision.RETRY, Decision.REROUTE]:
                stage = transition.from_stage
                failure_counts[stage] = failure_counts.get(stage, 0) + 1

        # Return stages with above-average failures
        if not failure_counts:
            return []

        avg_failures = sum(failure_counts.values()) / len(failure_counts)
        return [
            stage for stage, count in failure_counts.items() if count > avg_failures
        ]

    def export_graph(self, filename: str = "stage_graph.png") -> None:
        """Export stage graph visualization."""
        try:
            import matplotlib.pyplot as plt

            pos = nx.spring_layout(self.graph)

            # Color nodes based on status
            node_colors = []
            for node in self.graph.nodes():
                status = self.stage_status.get(node, StageStatus.NOT_STARTED)
                if status == StageStatus.COMPLETED:
                    node_colors.append("green")
                elif status == StageStatus.IN_PROGRESS:
                    node_colors.append("yellow")
                elif status == StageStatus.FAILED:
                    node_colors.append("red")
                else:
                    node_colors.append("lightgray")

            # Draw graph
            nx.draw(
                self.graph,
                pos,
                node_color=node_colors,
                node_size=1000,
                with_labels=True,
                font_size=10,
                font_weight="bold",
                arrows=True,
                edge_color="gray",
                arrowsize=20,
            )

            # Add edge labels for transition counts
            edge_labels = {}
            for (u, v), count in self.transition_counts.items():
                if self.graph.has_edge(u, v):
                    edge_labels[(u, v)] = str(count)

            nx.draw_networkx_edge_labels(self.graph, pos, edge_labels)

            plt.title("Stage Transition Graph")
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(filename, dpi=150, bbox_inches="tight")
            plt.close()

            logger.info(f"Graph exported to {filename}")

        except ImportError:
            logger.warning("matplotlib not available for graph export")


# Example usage and testing
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Create router with custom transitions
    custom_transitions = {
        ("research", "execute"): {
            "weight": 1.5,
            "reason": "Skip planning for simple tasks",
        },
        ("think", "decide"): {"weight": 2.0, "reason": "Fast track for clear problems"},
    }

    router = StageRouter(custom_transitions=custom_transitions)

    # Simulate some stage transitions
    test_decisions = [
        StrategyDecision(action=Decision.PROCEED, reason="Starting"),
        StrategyDecision(action=Decision.PROCEED, reason="Good research"),
        StrategyDecision(
            action=Decision.REROUTE, target_stage="research", reason="Need more info"
        ),
        StrategyDecision(action=Decision.PROCEED, reason="Research complete"),
        StrategyDecision(action=Decision.PROCEED, reason="Reflection done"),
        StrategyDecision(action=Decision.PROCEED, reason="Decision made"),
        StrategyDecision(action=Decision.RETRY, reason="Execution failed"),
        StrategyDecision(action=Decision.PROCEED, reason="Execution success"),
        StrategyDecision(
            action=Decision.REROUTE, target_stage="execute", reason="Validation failed"
        ),
    ]

    current = "think"
    router.set_current_stage(current)

    print("Simulating stage transitions:\n")
    for decision in test_decisions:
        next_stage = router.next_stage(current, decision)
        print(f"{current} -> {next_stage or 'END'} | {decision.reason}")
        if next_stage:
            current = next_stage
        else:
            break

    # Show analysis
    print("\nTransition Analysis:")
    analysis = router.get_transition_analysis()
    for key, value in analysis.items():
        print(f"  {key}: {value}")

    # Show stage status
    print("\nStage Status:")
    for stage, status in router.get_stage_status_summary().items():
        print(f"  {stage}: {status}")

    # Test path finding
    print(
        f"\nOptimal path from 'execute' to 'solidify': {router.suggest_optimal_path('execute')}"
    )
    print(
        f"Can skip from 'think' to 'execute': {router.can_skip_to('think', 'execute')}"
    )

    # Export graph (if matplotlib available)
    router.export_graph("test_stage_graph.png")
