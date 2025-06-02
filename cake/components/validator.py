#!/usr/bin/env python3
"""task_convergence_validator.py - Global Task Convergence Validation for CAKE

Ensures the entire TRRDEVS workflow actually solved the original problem,
not just completed all stages. Provides multi-layer validation with
semantic analysis, requirement tracking, and deliverable verification.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import asyncio
import difflib
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List

# Configure module logger
logger = logging.getLogger(__name__)


class ConvergenceStatus(Enum):
    """Status of task convergence validation."""

    CONVERGED = auto()  # Task fully solved
    PARTIAL = auto()  # Some requirements met
    DIVERGED = auto()  # Solution doesn't match task
    INCOMPLETE = auto()  # Missing critical components
    REGRESSED = auto()  # Solution broke existing functionality
    AMBIGUOUS = auto()  # Cannot determine convergence


@dataclass
class RequirementTrace:
    """
    Tracks a single requirement through the workflow.

    Attributes:
        id: Unique requirement identifier
        text: Original requirement text
        category: Type of requirement (functional, performance, etc.)
        priority: Critical, high, medium, low
        addressed_stages: Which stages addressed this requirement
        validation_evidence: Evidence of implementation
        status: Current fulfillment status
        confidence: 0.0-1.0 confidence in fulfillment
    """

    id: str
    text: str
    category: str
    priority: str
    addressed_stages: List[str] = field(default_factory=list)
    validation_evidence: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, addressed, validated, failed
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConvergenceReport:
    """
    Comprehensive report on task convergence.

    Attributes:
        status: Overall convergence status
        confidence: 0.0-1.0 overall confidence
        requirements_met: Percentage of requirements satisfied
        critical_gaps: List of unfulfilled critical requirements
        validation_summary: Summary of validation checks
        recommendations: Actionable recommendations
        evidence: Supporting evidence for the assessment
    """

    status: ConvergenceStatus
    confidence: float
    requirements_met: float
    critical_gaps: List[str]
    validation_summary: Dict[str, Any]
    recommendations: List[str]
    evidence: Dict[str, List[str]]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
            "status": self.status.name,
            "confidence": self.confidence,
            "requirements_met": self.requirements_met,
            "critical_gaps": self.critical_gaps,
            "validation_summary": self.validation_summary,
            "recommendations": self.recommendations,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }
        return data


class RequirementExtractor:
    """
    Extracts and categorizes requirements from task descriptions.
    """

    # Requirement detection patterns
    REQUIREMENT_PATTERNS = {
        "functional": [
            r"(?:must|should|shall|need to|required to)\s+(.+?)(?:\.|$)",
            r"(?:implement|create|build|develop|add)\s+(.+?)(?:\.|$)",
            r"(?:the system|application|code)\s+(?:must|should|will)\s+(.+?)(?:\.|$)",
        ],
        "performance": [
            r"(?:within|under|less than)\s+(\d+(?:\.\d+)?)\s*(ms|seconds?|minutes?)",
            r"(?:at least|minimum|more than)\s+(\d+)\s*(?:requests?|users?|transactions?)",
            r"(?:response time|latency|speed).*?(\d+(?:\.\d+)?)\s*(ms|seconds?)",
        ],
        "security": [
            r"(?:secure|encrypt|authenticate|authorize|permission)",
            r"(?:login|password|token|ssl|https|security)",
            r"(?:access control|user management|authentication)",
        ],
        "quality": [
            r"(?:test coverage|unit tests?|integration tests?)",
            r"(?:code quality|linting|formatting|style)",
            r"(?:documentation|comments|readme)",
        ],
        "deployment": [
            r"(?:deploy|production|staging|environment)",
            r"(?:docker|container|kubernetes|aws|cloud)",
            r"(?:ci/cd|pipeline|automation)",
        ],
    }

    # Priority indicators
    PRIORITY_INDICATORS = {
        "critical": ["critical", "essential", "must have", "required", "mandatory"],
        "high": ["important", "should have", "high priority", "needed"],
        "medium": ["would like", "nice to have", "medium priority"],
        "low": ["optional", "if time permits", "low priority", "future"],
    }

    def extract_requirements(self, task_description: str) -> List[RequirementTrace]:
        """
        Extract structured requirements from task description.

        Args:
            task_description: The original task description

        Returns:
            List of RequirementTrace objects
        """
        requirements = []

        # Split into sentences for processing
        sentences = re.split(r"[.!?]+", task_description)

        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check each category
            for category, patterns in self.REQUIREMENT_PATTERNS.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, sentence, re.IGNORECASE)
                    for match in matches:
                        req_text = match.group(0).strip()
                        if len(req_text) > 10:  # Filter out too-short matches

                            # Generate unique ID
                            req_id = self._generate_requirement_id(req_text, category)

                            # Determine priority
                            priority = self._determine_priority(sentence)

                            requirement = RequirementTrace(
                                id=req_id,
                                text=req_text,
                                category=category,
                                priority=priority,
                                metadata={
                                    "sentence_index": i,
                                    "original_sentence": sentence,
                                    "pattern_matched": pattern,
                                },
                            )
                            requirements.append(requirement)

        # Add implicit requirements based on keywords
        implicit_reqs = self._extract_implicit_requirements(task_description)
        requirements.extend(implicit_reqs)

        # Remove duplicates
        requirements = self._deduplicate_requirements(requirements)

        logger.info(f"Extracted {len(requirements)} requirements from task description")
        return requirements

    def _generate_requirement_id(self, text: str, category: str) -> str:
        """Generate unique requirement ID."""
        text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"{category}_{text_hash}"

    def _determine_priority(self, sentence: str) -> str:
        """Determine requirement priority from context."""
        sentence_lower = sentence.lower()

        for priority, indicators in self.PRIORITY_INDICATORS.items():
            if any(indicator in sentence_lower for indicator in indicators):
                return priority

        # Default priority based on language strength
        if any(word in sentence_lower for word in ["must", "required", "critical"]):
            return "critical"
        elif any(word in sentence_lower for word in ["should", "important"]):
            return "high"
        else:
            return "medium"

    def _extract_implicit_requirements(self, task_description: str) -> List[RequirementTrace]:
        """Extract implicit requirements based on task type."""
        implicit = []
        desc_lower = task_description.lower()

        # API development implies certain requirements
        if any(term in desc_lower for term in ["api", "endpoint", "rest"]):
            implicit.append(
                RequirementTrace(
                    id="implicit_api_tests",
                    text="API endpoints should have proper error handling and validation",
                    category="quality",
                    priority="high",
                    metadata={"type": "implicit", "inferred_from": "api_development"},
                )
            )

        # Web application implies security
        if any(term in desc_lower for term in ["web", "website", "webapp", "login"]):
            implicit.append(
                RequirementTrace(
                    id="implicit_web_security",
                    text="Web application should implement basic security measures",
                    category="security",
                    priority="critical",
                    metadata={"type": "implicit", "inferred_from": "web_development"},
                )
            )

        # Database mentions imply data integrity
        if any(term in desc_lower for term in ["database", "db", "sql", "data"]):
            implicit.append(
                RequirementTrace(
                    id="implicit_data_integrity",
                    text="Data operations should maintain consistency and integrity",
                    category="functional",
                    priority="critical",
                    metadata={"type": "implicit", "inferred_from": "database_usage"},
                )
            )

        return implicit

    def _deduplicate_requirements(
        self, requirements: List[RequirementTrace]
    ) -> List[RequirementTrace]:
        """Remove duplicate requirements using text similarity."""
        unique_reqs = []

        for req in requirements:
            is_duplicate = False

            for existing in unique_reqs:
                # Check text similarity
                similarity = difflib.SequenceMatcher(
                    None, req.text.lower(), existing.text.lower()
                ).ratio()

                if similarity > 0.8:  # 80% similarity threshold
                    # Merge metadata and keep higher priority
                    if self._priority_value(req.priority) > self._priority_value(existing.priority):
                        existing.priority = req.priority
                    existing.metadata.update(req.metadata)
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_reqs.append(req)

        return unique_reqs

    def _priority_value(self, priority: str) -> int:
        """Convert priority to numeric value for comparison."""
        return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(priority, 0)


class SolutionAnalyzer:
    """
    Analyzes the final solution against requirements.
    """

    def __init__(self, claude_client: Any):
        """Initialize with Claude client for semantic analysis."""
        self.client = claude_client

    async def analyze_solution(
        self,
        requirements: List[RequirementTrace],
        stage_outputs: Dict[str, Any],
        final_artifacts: List[str],
    ) -> Dict[str, Any]:
        """
        Analyze how well the solution addresses requirements.

        Args:
            requirements: List of extracted requirements
            stage_outputs: Outputs from each TRRDEVS stage
            final_artifacts: Final deliverables (code, docs, etc.)

        Returns:
            Analysis results with evidence and confidence scores
        """
        analysis = {
            "requirement_analysis": {},
            "code_analysis": {},
            "deliverable_analysis": {},
            "gap_analysis": {},
            "confidence_scores": {},
        }

        # Analyze each requirement
        for req in requirements:
            req_analysis = await self._analyze_requirement(req, stage_outputs, final_artifacts)
            analysis["requirement_analysis"][req.id] = req_analysis

        # Analyze code quality and completeness
        if final_artifacts:
            analysis["code_analysis"] = await self._analyze_code_quality(final_artifacts)

        # Analyze deliverables
        analysis["deliverable_analysis"] = await self._analyze_deliverables(
            stage_outputs, final_artifacts
        )

        # Identify gaps
        analysis["gap_analysis"] = self._identify_gaps(requirements, analysis)

        return analysis

    async def _analyze_requirement(
        self, req: RequirementTrace, stage_outputs: Dict[str, Any], artifacts: List[str]
    ) -> Dict[str, Any]:
        """Analyze how well a specific requirement was addressed."""
        # Collect relevant evidence
        evidence = []

        # Check stage outputs for mentions
        for stage, output in stage_outputs.items():
            if isinstance(output, str) and self._requirement_mentioned(req, output):
                evidence.append(f"Addressed in {stage}: {output[:200]}...")
                req.addressed_stages.append(stage)

        # Check artifacts
        for artifact in artifacts:
            if self._requirement_in_artifact(req, artifact):
                evidence.append(f"Implemented in artifact: {artifact[:100]}...")

        # Use Claude for semantic analysis
        semantic_analysis = await self._semantic_requirement_check(req, evidence)

        # Calculate confidence
        confidence = self._calculate_requirement_confidence(req, evidence, semantic_analysis)

        return {
            "requirement": req.text,
            "category": req.category,
            "priority": req.priority,
            "evidence": evidence,
            "semantic_analysis": semantic_analysis,
            "confidence": confidence,
            "status": "addressed" if confidence > 0.7 else "incomplete",
        }

    def _requirement_mentioned(self, req: RequirementTrace, text: str) -> bool:
        """Check if requirement is mentioned in text."""
        req_keywords = set(re.findall(r"\w+", req.text.lower()))
        text_keywords = set(re.findall(r"\w+", text.lower()))

        # Remove common words
        common_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        req_keywords -= common_words
        text_keywords -= common_words

        # Check overlap
        if len(req_keywords) == 0:
            return False

        overlap = len(req_keywords & text_keywords) / len(req_keywords)
        return overlap > 0.3  # 30% keyword overlap

    def _requirement_in_artifact(self, req: RequirementTrace, artifact: str) -> bool:
        """Check if requirement is implemented in artifact."""  # For now, use keyword matching
        # In production, would use AST analysis for code
        return self._requirement_mentioned(req, artifact)

    async def _semantic_requirement_check(
        self, req: RequirementTrace, evidence: List[str]
    ) -> Dict[str, Any]:
        """Use Claude to semantically analyze requirement fulfillment."""
        prompt = f"""
        Analyze whether this requirement has been adequately addressed:
        
        REQUIREMENT: {req.text}
        CATEGORY: {req.category}
        PRIORITY: {req.priority}
        
        EVIDENCE:
        {chr(10).join(f"- {e}" for e in evidence)}
        
        Provide:
        1. FULFILLED: yes/no/partial
        2. CONFIDENCE: 0.0-1.0
        3. REASONING: Brief explanation
        4. MISSING: What's still needed (if any)
        
        Be precise and critical. Partial implementation = partial.
        """

        try:
            response = await self.client.chat(prompt, max_tokens=300)
            return self._parse_semantic_response(response.content)
        except Exception as e:
            logger.error(f"Semantic analysis failed: {e}")
            return {
                "fulfilled": "unknown",
                "confidence": 0.0,
                "reasoning": "Analysis failed",
                "missing": ["Could not analyze"],
            }

    def _parse_semantic_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's semantic analysis response."""
        result = {
            "fulfilled": "unknown",
            "confidence": 0.0,
            "reasoning": "",
            "missing": [],
        }

        # Extract structured data
        if match := re.search(r"FULFILLED:\s*(yes|no|partial)", response, re.IGNORECASE):
            result["fulfilled"] = match.group(1).lower()

        if match := re.search(r"CONFIDENCE:\s*(\d*\.?\d+)", response):
            result["confidence"] = float(match.group(1))

        if match := re.search(r"REASONING:\s*(.+?)(?=MISSING:|$)", response, re.DOTALL):
            result["reasoning"] = match.group(1).strip()

        if match := re.search(r"MISSING:\s*(.+)", response, re.DOTALL):
            missing_text = match.group(1).strip()
            result["missing"] = [item.strip() for item in missing_text.split("\n") if item.strip()]

        return result

    def _calculate_requirement_confidence(
        self, req: RequirementTrace, evidence: List[str], semantic: Dict[str, Any]
    ) -> float:
        """Calculate overall confidence in requirement fulfillment."""
        # Base confidence from semantic analysis
        base_confidence = semantic.get("confidence", 0.0)

        # Adjust based on evidence quantity
        evidence_bonus = min(len(evidence) * 0.1, 0.3)

        # Adjust based on requirement priority
        priority_weight = {
            "critical": 1.0,  # No bonus for critical (must be perfect)
            "high": 1.1,
            "medium": 1.2,
            "low": 1.3,
        }.get(req.priority, 1.0)

        # Penalty for semantic analysis saying "no" or "partial"
        fulfillment_modifier = {
            "yes": 1.0,
            "partial": 0.6,
            "no": 0.1,
            "unknown": 0.3,
        }.get(semantic.get("fulfilled", "unknown"), 0.3)

        confidence = (base_confidence + evidence_bonus) * priority_weight * fulfillment_modifier

        return min(confidence, 1.0)

    async def _analyze_code_quality(self, artifacts: List[str]) -> Dict[str, Any]:
        """Analyze code quality and completeness."""
        quality_checks = {
            "has_tests": False,
            "has_documentation": False,
            "has_error_handling": False,
            "follows_conventions": False,
            "is_complete": False,
        }

        # Simple pattern-based checks
        combined_artifacts = "\n".join(artifacts)

        # Check for tests
        if any(
            pattern in combined_artifacts.lower()
            for pattern in ["test_", "def test", "unittest", "pytest"]
        ):
            quality_checks["has_tests"] = True

        # Check for documentation
        if any(pattern in combined_artifacts for pattern in ['"""', "'''", "# ", "README"]):
            quality_checks["has_documentation"] = True

        # Check for error handling
        if any(pattern in combined_artifacts for pattern in ["try:", "except:", "raise", "assert"]):
            quality_checks["has_error_handling"] = True

        # More sophisticated analysis could go here

        return quality_checks

    async def _analyze_deliverables(
        self, stage_outputs: Dict[str, Any], artifacts: List[str]
    ) -> Dict[str, Any]:
        """Analyze completeness of deliverables."""
        return {
            "total_stages_completed": len([s for s in stage_outputs.values() if s]),
            "artifacts_generated": len(artifacts),
            "has_final_implementation": len(artifacts) > 0,
            "execution_successful": "execute" in stage_outputs and stage_outputs["execute"],
            "validation_passed": "validate" in stage_outputs
            and "success" in str(stage_outputs.get("validate", "")).lower(),
        }

    def _identify_gaps(
        self, requirements: List[RequirementTrace], analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Identify gaps between requirements and implementation."""
        gaps = {
            "unfulfilled_critical": [],
            "unfulfilled_high": [],
            "low_confidence": [],
            "missing_evidence": [],
        }

        for req in requirements:
            req_analysis = analysis["requirement_analysis"].get(req.id, {})
            confidence = req_analysis.get("confidence", 0.0)

            if confidence < 0.5:
                if req.priority == "critical":
                    gaps["unfulfilled_critical"].append(req.text)
                elif req.priority == "high":
                    gaps["unfulfilled_high"].append(req.text)

            if confidence < 0.7:
                gaps["low_confidence"].append(req.text)

            if len(req_analysis.get("evidence", [])) == 0:
                gaps["missing_evidence"].append(req.text)

        return gaps


class TaskConvergenceValidator:
    """
    Main validator that orchestrates requirement extraction, analysis, and reporting.
    """

    def __init__(self, claude_client: Any):
        """Initialize validator with Claude client."""
        self.client = claude_client
        self.extractor = RequirementExtractor()
        self.analyzer = SolutionAnalyzer(claude_client)

        # Validation thresholds
        self.thresholds = {
            "min_critical_confidence": 0.9,  # Critical requirements must be 90% confident
            "min_high_confidence": 0.8,  # High priority requirements 80%
            "min_overall_confidence": 0.75,  # Overall solution confidence
            "min_requirements_met": 0.8,  # 80% of requirements addressed
        }

        logger.info("TaskConvergenceValidator initialized")

    async def validate_convergence(
        self,
        original_task: str,
        stage_outputs: Dict[str, Any],
        final_artifacts: List[str],
    ) -> ConvergenceReport:
        """
        Validate whether the solution converges on the original task.

        Args:
            original_task: The original task description
            stage_outputs: Outputs from each TRRDEVS stage
            final_artifacts: Final code/documentation artifacts

        Returns:
            ConvergenceReport with detailed analysis
        """
        logger.info("Starting task convergence validation")

        # Extract requirements from original task
        requirements = self.extractor.extract_requirements(original_task)
        logger.info(f"Extracted {len(requirements)} requirements")

        # Analyze solution against requirements
        analysis = await self.analyzer.analyze_solution(
            requirements, stage_outputs, final_artifacts
        )

        # Generate convergence report
        report = self._generate_report(requirements, analysis, original_task)

        logger.info(
            f"Convergence validation complete: {report.status.name} ({report.confidence:.1%})"
        )

        return report

    def _generate_report(
        self,
        requirements: List[RequirementTrace],
        analysis: Dict[str, Any],
        original_task: str,
    ) -> ConvergenceReport:
        """Generate comprehensive convergence report."""
        # Calculate metrics
        total_requirements = len(requirements)
        critical_reqs = [r for r in requirements if r.priority == "critical"]
        high_reqs = [r for r in requirements if r.priority == "high"]

        # Calculate fulfillment rates
        fulfilled_count = 0
        critical_fulfilled = 0
        high_fulfilled = 0
        total_confidence = 0.0

        critical_gaps = []
        low_confidence_items = []

        for req in requirements:
            req_analysis = analysis["requirement_analysis"].get(req.id, {})
            confidence = req_analysis.get("confidence", 0.0)
            total_confidence += confidence

            if confidence >= 0.7:
                fulfilled_count += 1

                if req.priority == "critical":
                    critical_fulfilled += 1
                elif req.priority == "high":
                    high_fulfilled += 1
            else:
                if req.priority in ["critical", "high"]:
                    critical_gaps.append(f"{req.priority.upper()}: {req.text}")

                if confidence < 0.5:
                    low_confidence_items.append(req.text)

        # Calculate overall metrics
        requirements_met = fulfilled_count / total_requirements if total_requirements > 0 else 0.0
        avg_confidence = total_confidence / total_requirements if total_requirements > 0 else 0.0
        critical_success_rate = critical_fulfilled / len(critical_reqs) if critical_reqs else 1.0
        high_success_rate = high_fulfilled / len(high_reqs) if high_reqs else 1.0

        # Determine convergence status
        status = self._determine_status(
            requirements_met, avg_confidence, critical_success_rate, high_success_rate
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            critical_gaps, low_confidence_items, analysis, requirements_met
        )

        # Collect evidence
        evidence = {
            "requirements_extracted": [r.text for r in requirements],
            "critical_requirements": [r.text for r in critical_reqs],
            "high_priority_requirements": [r.text for r in high_reqs],
            "fulfilled_requirements": [
                r.text
                for r in requirements
                if analysis["requirement_analysis"].get(r.id, {}).get("confidence", 0) >= 0.7
            ],
        }

        # Create validation summary
        validation_summary = {
            "total_requirements": total_requirements,
            "requirements_met_percentage": requirements_met * 100,
            "average_confidence": avg_confidence,
            "critical_success_rate": critical_success_rate,
            "high_priority_success_rate": high_success_rate,
            "code_quality_checks": analysis.get("code_analysis", {}),
            "deliverable_completeness": analysis.get("deliverable_analysis", {}),
            "gap_analysis": analysis.get("gap_analysis", {}),
        }

        return ConvergenceReport(
            status=status,
            confidence=avg_confidence,
            requirements_met=requirements_met,
            critical_gaps=critical_gaps,
            validation_summary=validation_summary,
            recommendations=recommendations,
            evidence=evidence,
        )

    def _determine_status(
        self,
        requirements_met: float,
        avg_confidence: float,
        critical_success: float,
        high_success: float,
    ) -> ConvergenceStatus:
        """Determine overall convergence status based on metrics."""
        # Critical requirements must be met
        if critical_success < self.thresholds["min_critical_confidence"]:
            return ConvergenceStatus.DIVERGED

        # Check overall thresholds
        if (
            requirements_met >= self.thresholds["min_requirements_met"]
            and avg_confidence >= self.thresholds["min_overall_confidence"]
            and high_success >= self.thresholds["min_high_confidence"]
        ):
            return ConvergenceStatus.CONVERGED

        # Partial success
        if requirements_met >= 0.6 and avg_confidence >= 0.6:
            return ConvergenceStatus.PARTIAL

        # Low success
        if requirements_met >= 0.3:
            return ConvergenceStatus.INCOMPLETE

        # Very low success
        return ConvergenceStatus.DIVERGED

    def _generate_recommendations(
        self,
        critical_gaps: List[str],
        low_confidence: List[str],
        analysis: Dict[str, Any],
        requirements_met: float,
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Critical gaps
        if critical_gaps:
            recommendations.append(
                f"🚨 CRITICAL: Address {len(critical_gaps)} unfulfilled critical requirements"
            )
            for gap in critical_gaps[:3]:  # Show top 3
                recommendations.append(f"   - {gap}")

        # Low confidence items
        if low_confidence:
            recommendations.append(
                f"⚠️  REVIEW: {len(low_confidence)} requirements have low confidence scores"
            )

        # Code quality issues
        code_analysis = analysis.get("code_analysis", {})
        if not code_analysis.get("has_tests", False):
            recommendations.append("📝 ADD: Implement comprehensive tests")

        if not code_analysis.get("has_error_handling", False):
            recommendations.append("🛡️  ADD: Implement proper error handling")

        # Overall assessment
        if requirements_met < 0.5:
            recommendations.append(
                "🔄 RESTART: Consider re-approaching the problem from the 'think' stage"
            )
        elif requirements_met < 0.8:
            recommendations.append("🔧 ITERATE: Return to 'execute' stage to address gaps")

        # Deliverable issues
        deliverable_analysis = analysis.get("deliverable_analysis", {})
        if not deliverable_analysis.get("has_final_implementation", False):
            recommendations.append("💻 IMPLEMENT: No final implementation artifacts found")

        return recommendations


# Example usage and testing
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Mock Claude client for testing
    class MockClaudeClient:
        async def chat(self, prompt: str, max_tokens: int = 300):
            # Simulate Claude response for semantic analysis
            from types import SimpleNamespace

            if "authentication" in prompt.lower():
                content = """
                FULFILLED: yes
                CONFIDENCE: 0.85
                REASONING: The solution implements login functionality with password hashing and session management
                MISSING: Two-factor authentication not implemented
                """
            else:
                content = """FULFILLED: partial
                CONFIDENCE: 0.6
                REASONING: Basic functionality is present but lacks comprehensive implementation
                MISSING: Error handling, validation, edge case coverage
                """

            return SimpleNamespace(content=content)

    # Test the validator
    async def test_validator():
        client = MockClaudeClient()
        validator = TaskConvergenceValidator(client)

        # Test task
        original_task = """Create a REST API for user authentication that must:
        - Implement secure login with password hashing
        - Provide JWT token-based authentication
        - Include user registration endpoint
        - Add proper input validation
        - Have comprehensive test coverage
        - Deploy to production environment
        """

        # Mock stage outputs
        stage_outputs = {
            "think": "Analyzed requirements for authentication API",
            "research": "Researched JWT libraries and security best practices",
            "reflect": "Considered security implications and validation needs",
            "decide": "Chose FastAPI with bcrypt for password hashing",
            "execute": "Implemented login, registration, and token endpoints",
            "validate": "All tests passing, security tests included",
            "solidify": "Documentation complete, ready for deployment",
        }

        # Mock artifacts
        final_artifacts = [
            """from fastapi import FastAPI, HTTPException
            import bcrypt
            import jwt
            
            app = FastAPI()
            
            @app.post("/register")
            def register(user_data):
                # Hash password
                hashed = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt())
                # Save user...
                return {"message": "User created"}
            
            @app.post("/login")
            def login(credentials):
                # Validate credentials
                if validate_user(credentials):
                    token = jwt.encode({"user_id": user.id}, "secret")
                    return {"token": token}
                raise HTTPException(401, "Invalid credentials")
            
            def test_login():
                # Test implementation
                assert login_endpoint_works()
            """,
            """# API Documentation
            ## Authentication Endpoints
            - POST /register - Create new user
            - POST /login - Authenticate user
            """,
        ]

        # Run validation
        report = await validator.validate_convergence(original_task, stage_outputs, final_artifacts)

        print("=== TASK CONVERGENCE VALIDATION REPORT ===")
        print(f"Status: {report.status.name}")
        print(f"Confidence: {report.confidence:.1%}")
        print(f"Requirements Met: {report.requirements_met:.1%}")
        print(f"\nCritical Gaps: {len(report.critical_gaps)}")
        for gap in report.critical_gaps:
            print(f"  - {gap}")

        print(f"\nRecommendations:")
        for rec in report.recommendations:
            print(f"  - {rec}")

        print(f"\nValidation Summary:")
        for key, value in report.validation_summary.items():
            print(f"  {key}: {value}")

    # Run test
    asyncio.run(test_validator())
