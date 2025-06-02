#!/usr/bin/env python3
"""
claude_prompt_orchestration.py - Intelligent Prompt Engineering for CAKE

Provides sophisticated prompt construction, optimization, and management for
Claude interactions. Uses templates, context injection, response parsing,
and adaptive prompt strategies to maximize Claude's effectiveness.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import re
import json
import logging
import asyncio
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum, auto
from collections import defaultdict, deque
import pickle
from string import Template
import yaml

# Configure module logger
logger = logging.getLogger(__name__)


class PromptType(Enum):
    """Types of prompts for different purposes."""
    STAGE_EXECUTION = auto()      # Execute TRRDEVS stage
    ERROR_ANALYSIS = auto()       # Analyze and fix errors
    CODE_GENERATION = auto()      # Generate code solutions
    INFORMATION_SYNTHESIS = auto() # Synthesize research information
    DECISION_MAKING = auto()      # Make strategic decisions
    VALIDATION = auto()           # Validate outputs and results
    REFLECTION = auto()           # Reflect on approaches
    OPTIMIZATION = auto()         # Optimize existing solutions
    EXPLANATION = auto()          # Explain complex concepts
    DEBUGGING = auto()            # Debug specific issues


class ResponseQuality(Enum):
    """Quality levels of Claude responses."""
    EXCELLENT = auto()    # Perfect response, exactly what was needed
    GOOD = auto()        # Good response, minor issues
    ADEQUATE = auto()    # Adequate but could be better
    POOR = auto()        # Poor response, major issues
    UNUSABLE = auto()    # Completely unusable response


@dataclass
class PromptTemplate:
    """
    Structured prompt template with metadata.
    
    Attributes:
        template_id: Unique identifier
        prompt_type: Type of prompt
        template_text: Template string with placeholders
        required_variables: Variables that must be provided
        optional_variables: Variables that enhance the prompt
        success_metrics: Criteria for measuring success
        optimization_notes: Notes for improving the template
        usage_statistics: Statistics about template usage
        version: Template version for tracking changes
    """
    template_id: str
    prompt_type: PromptType
    template_text: str
    required_variables: Set[str]
    optional_variables: Set[str] = field(default_factory=set)
    success_metrics: Dict[str, float] = field(default_factory=dict)
    optimization_notes: List[str] = field(default_factory=list)
    usage_statistics: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def render(self, variables: Dict[str, Any]) -> str:
        """Render template with provided variables."""
        # Check required variables
        missing = self.required_variables - set(variables.keys())
        if missing:
            raise ValueError(f"Missing required variables: {missing}")
        
        # Use safe substitute to handle missing optional variables
        template = Template(self.template_text)
        return template.safe_substitute(variables)


@dataclass
class PromptContext:
    """
    Context information for prompt construction.
    
    Attributes:
        stage: Current TRRDEVS stage
        task_description: Original task description
        domain: Domain of the task
        error_context: Current error information
        previous_attempts: Previous attempts and their outcomes
        available_tools: Tools available in the environment
        constraints: Constraints on the solution
        preferences: User/domain preferences
        knowledge_retrieved: Retrieved knowledge from ledger
        time_constraints: Time limitations
        cost_constraints: Cost limitations
        quality_requirements: Quality requirements
    """
    stage: str
    task_description: str
    domain: str
    error_context: Optional[Dict[str, Any]] = None
    previous_attempts: List[Dict[str, Any]] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    knowledge_retrieved: List[Dict[str, Any]] = field(default_factory=list)
    time_constraints: Optional[Dict[str, Any]] = None
    cost_constraints: Optional[Dict[str, Any]] = None
    quality_requirements: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptExecution:
    """
    Record of a prompt execution and its results.
    
    Attributes:
        execution_id: Unique execution identifier
        template_id: Template used
        rendered_prompt: Final prompt sent to Claude
        context: Context used for prompt construction
        response: Claude's response
        response_quality: Assessed quality of response
        execution_time: Time taken for execution
        token_usage: Tokens used in request/response
        cost: Cost of the execution
        success_indicators: Metrics indicating success
        failure_indicators: Metrics indicating failure
        lessons_learned: Lessons from this execution
    """
    execution_id: str
    template_id: str
    rendered_prompt: str
    context: PromptContext
    response: str
    response_quality: ResponseQuality
    execution_time: float
    token_usage: Dict[str, int]
    cost: float
    success_indicators: Dict[str, float] = field(default_factory=dict)
    failure_indicators: Dict[str, float] = field(default_factory=dict)
    lessons_learned: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptTemplateLibrary:
    """
    Library of optimized prompt templates for different scenarios.
    """
    
    def __init__(self, templates_path: Optional[Path] = None):
        """Initialize template library."""
        self.templates: Dict[str, PromptTemplate] = {}
        self.templates_by_type: Dict[PromptType, List[str]] = defaultdict(list)
        self.templates_path = templates_path
        
        # Load default templates
        self._load_default_templates()
        
        # Load custom templates if path provided
        if templates_path:
            self._load_custom_templates()
    
    def _load_default_templates(self):
        """Load default prompt templates."""
        
        # Stage execution templates
        self.add_template(PromptTemplate(
            template_id="stage_execute_coding",
            prompt_type=PromptType.STAGE_EXECUTION,
            template_text="""
You are executing the EXECUTE stage of the TRRDEVS methodology for this task:

**TASK**: $task_description

**DOMAIN**: $domain

**STAGE CONTEXT**: 
- Current stage: EXECUTE
- Previous stages completed: $previous_stages
- Available tools: $available_tools

**REQUIREMENTS**:
$requirements_context

**CONSTRAINTS**:
$constraints_context

**APPROACH DECIDED**:
$decided_approach

Your job is to implement the solution following the decided approach. 

**IMPORTANT GUIDELINES**:
1. Write complete, working code
2. Include proper error handling
3. Add meaningful comments
4. Follow $domain best practices
5. Test your implementation
6. Provide clear documentation

**OUTPUT FORMAT**:
1. **IMPLEMENTATION**: [Complete code implementation]
2. **TESTING**: [How to test the implementation]
3. **DOCUMENTATION**: [Usage instructions and examples]
4. **NOTES**: [Any important considerations or limitations]

Begin implementation:
""",
            required_variables={"task_description", "domain", "decided_approach"},
            optional_variables={"previous_stages", "available_tools", "requirements_context", "constraints_context"}
        ))
        
        # Error analysis template
        self.add_template(PromptTemplate(
            template_id="error_analysis_comprehensive",
            prompt_type=PromptType.ERROR_ANALYSIS,
            template_text="""
You are analyzing an error that occurred during $stage stage of development.

**ORIGINAL TASK**: $task_description

**ERROR DETAILS**:
```
$error_message
```

**CONTEXT**:
- Stage: $stage
- Domain: $domain
- Previous attempts: $previous_attempts_count
- Available tools: $available_tools

**ERROR CLASSIFICATION**:
$error_classification

**RETRIEVED KNOWLEDGE**:
$knowledge_context

**ANALYSIS REQUIRED**:
1. **ROOT CAUSE**: What is the fundamental cause of this error?
2. **IMMEDIATE CAUSE**: What directly triggered this error?
3. **CONTEXT FACTORS**: What environmental/contextual factors contributed?
4. **SOLUTION STRATEGY**: What's the best approach to fix this?
5. **PREVENTION**: How can we prevent this error in the future?

**OUTPUT FORMAT**:
```json
{
  "root_cause": "...",
  "immediate_cause": "...",
  "context_factors": ["...", "..."],
  "solution_strategy": "...",
  "recommended_actions": [
    {
      "action": "...",
      "command": "...",
      "reasoning": "...",
      "confidence": 0.9
    }
  ],
  "prevention_measures": ["...", "..."],
  "estimated_fix_time": "...",
  "confidence_level": 0.8
}
```

Analyze the error:
""",
            required_variables={"stage", "task_description", "error_message", "domain"},
            optional_variables={"previous_attempts_count", "available_tools", "error_classification", "knowledge_context"}
        ))
        
        # Code generation template
        self.add_template(PromptTemplate(
            template_id="code_generation_structured",
            prompt_type=PromptType.CODE_GENERATION,
            template_text="""
Generate code to solve this specific problem:

**PROBLEM**: $problem_description

**REQUIREMENTS**:
$requirements

**DOMAIN**: $domain

**TECHNICAL CONSTRAINTS**:
- Language: $language
- Framework/Libraries: $frameworks
- Performance requirements: $performance_requirements
- Security requirements: $security_requirements

**CONTEXT**:
$context_information

**QUALITY STANDARDS**:
- Code must be production-ready
- Include comprehensive error handling
- Add meaningful docstrings and comments
- Follow $domain coding standards
- Include type hints (if applicable)
- Write testable code

**DELIVERABLES**:
1. **MAIN IMPLEMENTATION**: Complete working code
2. **TESTS**: Unit tests covering key functionality
3. **DOCUMENTATION**: API documentation and usage examples
4. **DEPLOYMENT**: Setup/installation instructions

**OUTPUT FORMAT**:
```python
# IMPLEMENTATION
# [Your complete code here]

# TESTS
# [Your test code here]

# USAGE EXAMPLE
# [Example of how to use the code]
```

**EXPLANATION**:
[Explain your approach, key decisions, and any trade-offs]

Generate the code:
""",
            required_variables={"problem_description", "requirements", "domain", "language"},
            optional_variables={"frameworks", "performance_requirements", "security_requirements", "context_information"}
        ))
        
        # Decision making template
        self.add_template(PromptTemplate(
            template_id="decision_strategic",
            prompt_type=PromptType.DECISION_MAKING,
            template_text="""
You need to make a strategic decision for this development task.

**SITUATION**:
- Task: $task_description
- Current stage: $stage
- Domain: $domain

**DECISION CONTEXT**:
$decision_context

**AVAILABLE OPTIONS**:
$available_options

**CONSTRAINTS**:
- Budget: $budget_constraints
- Time: $time_constraints
- Quality requirements: $quality_requirements
- Risk tolerance: $risk_tolerance

**EVALUATION CRITERIA**:
1. **Feasibility**: How realistic is this option?
2. **Quality**: What quality of outcome can we expect?
3. **Speed**: How quickly can this be implemented?
4. **Cost**: What are the resource requirements?
5. **Risk**: What are the potential risks?
6. **Maintainability**: How easy is this to maintain long-term?

**PREVIOUS EXPERIENCE**:
$knowledge_from_ledger

**OUTPUT FORMAT**:
```json
{
  "recommended_option": "...",
  "confidence": 0.85,
  "reasoning": "...",
  "evaluation_matrix": {
    "option_1": {
      "feasibility": 0.9,
      "quality": 0.8,
      "speed": 0.7,
      "cost": 0.6,
      "risk": 0.8,
      "maintainability": 0.9,
      "overall_score": 0.78
    }
  },
  "implementation_plan": [
    {
      "step": "...",
      "estimated_time": "...",
      "dependencies": ["..."],
      "risks": ["..."]
    }
  ],
  "success_criteria": ["...", "..."],
  "fallback_plan": "..."
}
```

Make your decision:
""",
            required_variables={"task_description", "stage", "domain", "decision_context", "available_options"},
            optional_variables={"budget_constraints", "time_constraints", "quality_requirements", "risk_tolerance", "knowledge_from_ledger"}
        ))
        
        # Validation template
        self.add_template(PromptTemplate(
            template_id="validation_comprehensive",
            prompt_type=PromptType.VALIDATION,
            template_text="""
Validate this implementation against the original requirements.

**ORIGINAL TASK**: $task_description

**IMPLEMENTATION TO VALIDATE**:
```
$implementation_code
```

**REQUIREMENTS**:
$requirements

**QUALITY STANDARDS**:
$quality_standards

**DOMAIN**: $domain

**VALIDATION CHECKLIST**:
1. **FUNCTIONAL CORRECTNESS**: Does it solve the stated problem?
2. **REQUIREMENT COMPLIANCE**: Does it meet all requirements?
3. **CODE QUALITY**: Is the code well-written and maintainable?
4. **ERROR HANDLING**: Are edge cases and errors handled properly?
5. **PERFORMANCE**: Does it meet performance requirements?
6. **SECURITY**: Are there any security vulnerabilities?
7. **TESTING**: Is the implementation properly testable?
8. **DOCUMENTATION**: Is it adequately documented?

**VALIDATION APPROACH**:
- Analyze code statically
- Identify potential issues
- Suggest test cases
- Recommend improvements

**OUTPUT FORMAT**:
```json
{
  "validation_result": "PASS|FAIL|CONDITIONAL",
  "overall_score": 0.85,
  "detailed_scores": {
    "functional_correctness": 0.9,
    "requirement_compliance": 0.8,
    "code_quality": 0.9,
    "error_handling": 0.7,
    "performance": 0.8,
    "security": 0.9,
    "testing": 0.8,
    "documentation": 0.7
  },
  "identified_issues": [
    {
      "category": "error_handling",
      "severity": "medium",
      "description": "...",
      "location": "line 42",
      "recommendation": "..."
    }
  ],
  "recommended_tests": [
    {
      "test_type": "unit",
      "description": "...",
      "priority": "high"
    }
  ],
  "improvements": [
    {
      "area": "performance",
      "suggestion": "...",
      "impact": "medium"
    }
  ],
  "approval_conditions": ["...", "..."],
  "confidence": 0.9
}
```

Validate the implementation:
""",
            required_variables={"task_description", "implementation_code", "requirements", "domain"},
            optional_variables={"quality_standards"}
        ))
        
        # Reflection template
        self.add_template(PromptTemplate(
            template_id="reflection_process",
            prompt_type=PromptType.REFLECTION,
            template_text="""
Reflect on the current approach and progress for this task.

**TASK**: $task_description

**CURRENT PROGRESS**:
- Stages completed: $completed_stages
- Current stage: $current_stage
- Time elapsed: $time_elapsed
- Cost so far: $cost_so_far

**CURRENT APPROACH**:
$current_approach

**CHALLENGES ENCOUNTERED**:
$challenges

**RESULTS SO FAR**:
$current_results

**REFLECTION QUESTIONS**:
1. **APPROACH EFFECTIVENESS**: Is the current approach working well?
2. **PROGRESS QUALITY**: Is the progress meeting expectations?
3. **RESOURCE EFFICIENCY**: Are we using resources efficiently?
4. **RISK ASSESSMENT**: What risks do we face moving forward?
5. **ALTERNATIVE APPROACHES**: Should we consider different approaches?
6. **LEARNING OPPORTUNITIES**: What have we learned so far?

**DOMAIN CONTEXT**: $domain

**AVAILABLE KNOWLEDGE**:
$knowledge_context

**OUTPUT FORMAT**:
```json
{
  "overall_assessment": "excellent|good|fair|poor",
  "approach_effectiveness": 0.8,
  "progress_quality": 0.7,
  "resource_efficiency": 0.9,
  "confidence_in_success": 0.85,
  "key_insights": ["...", "..."],
  "identified_risks": [
    {
      "risk": "...",
      "probability": 0.3,
      "impact": "high",
      "mitigation": "..."
    }
  ],
  "recommendations": [
    {
      "action": "continue|adjust|pivot",
      "reasoning": "...",
      "priority": "high|medium|low"
    }
  ],
  "alternative_approaches": [
    {
      "approach": "...",
      "pros": ["...", "..."],
      "cons": ["...", "..."],
      "recommendation": "consider|explore|abandon"
    }
  ],
  "lessons_learned": ["...", "..."],
  "next_steps": ["...", "..."]
}
```

Reflect on the current state:
""",
            required_variables={"task_description", "current_stage", "current_approach", "domain"},
            optional_variables={"completed_stages", "time_elapsed", "cost_so_far", "challenges", "current_results", "knowledge_context"}
        ))
        
        logger.info(f"Loaded {len(self.templates)} default prompt templates")
    
    def add_template(self, template: PromptTemplate):
        """Add a template to the library."""
        self.templates[template.template_id] = template
        self.templates_by_type[template.prompt_type].append(template.template_id)
    
    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a template by ID."""
        return self.templates.get(template_id)
    
    def get_templates_by_type(self, prompt_type: PromptType) -> List[PromptTemplate]:
        """Get all templates of a specific type."""
        template_ids = self.templates_by_type.get(prompt_type, [])
        return [self.templates[tid] for tid in template_ids if tid in self.templates]
    
    def find_best_template(self, 
                          prompt_type: PromptType,
                          context: PromptContext) -> Optional[PromptTemplate]:
        """Find the best template for given type and context."""
        candidates = self.get_templates_by_type(prompt_type)
        
        if not candidates:
            return None
        
        # For now, use simple heuristics
        # In production, this could use ML to select optimal templates
        
        # Score templates based on success metrics and context match
        scored_templates = []
        for template in candidates:
            score = self._score_template_for_context(template, context)
            scored_templates.append((template, score))
        
        # Return highest scoring template
        scored_templates.sort(key=lambda x: x[1], reverse=True)
        return scored_templates[0][0] if scored_templates else None
    
    def _score_template_for_context(self, template: PromptTemplate, context: PromptContext) -> float:
        """Score how well a template matches the context."""
        score = 0.0
        
        # Base score from success metrics
        if template.success_metrics:
            score += template.success_metrics.get('average_quality', 0.5)
        else:
            score += 0.5  # Default for new templates
        
        # Domain-specific scoring
        if context.domain in template.template_text.lower():
            score += 0.2
        
        # Stage-specific scoring
        if context.stage in template.template_text.lower():
            score += 0.1
        
        # Complexity matching
        if context.error_context and 'error' in template.template_text.lower():
            score += 0.15
        
        # Knowledge availability
        if context.knowledge_retrieved and 'knowledge' in template.template_text.lower():
            score += 0.1
        
        return min(1.0, score)
    
    def _load_custom_templates(self):
        """Load custom templates from YAML files."""
        if not self.templates_path or not self.templates_path.exists():
            return
        
        for yaml_file in self.templates_path.glob("*.yaml"):
            try:
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)
                
                for template_data in data.get('templates', []):
                    template = PromptTemplate(
                        template_id=template_data['template_id'],
                        prompt_type=PromptType[template_data['prompt_type']],
                        template_text=template_data['template_text'],
                        required_variables=set(template_data.get('required_variables', [])),
                        optional_variables=set(template_data.get('optional_variables', [])),
                        version=template_data.get('version', '1.0')
                    )
                    self.add_template(template)
                
                logger.info(f"Loaded custom templates from {yaml_file}")
                
            except Exception as e:
                logger.error(f"Failed to load templates from {yaml_file}: {e}")


class ContextEnhancer:
    """
    Enhances prompt context with relevant information from various sources.
    """
    
    def __init__(self):
        """Initialize context enhancer."""
        self.enhancement_strategies = {
            'error_context': self._enhance_error_context,
            'knowledge_context': self._enhance_knowledge_context,
            'domain_context': self._enhance_domain_context,
            'constraints_context': self._enhance_constraints_context,
            'history_context': self._enhance_history_context
        }
    
    def enhance_context(self, 
                       base_context: PromptContext,
                       available_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance context with additional relevant information.
        
        Args:
            base_context: Base context to enhance
            available_data: Available data sources for enhancement
            
        Returns:
            Dictionary of enhanced context variables
        """
        enhanced = {
            'task_description': base_context.task_description,
            'domain': base_context.domain,
            'stage': base_context.stage
        }
        
        # Apply enhancement strategies
        for strategy_name, strategy_func in self.enhancement_strategies.items():
            try:
                enhancements = strategy_func(base_context, available_data)
                enhanced.update(enhancements)
            except Exception as e:
                logger.warning(f"Enhancement strategy {strategy_name} failed: {e}")
        
        return enhanced
    
    def _enhance_error_context(self, context: PromptContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance context with error information."""
        if not context.error_context:
            return {}
        
        error_classification = data.get('error_classification', {})
        
        enhanced = {
            'error_message': context.error_context.get('error', 'No error message'),
            'error_classification': self._format_error_classification(error_classification),
            'previous_attempts_count': len(context.previous_attempts),
        }
        
        # Add error-specific context
        if context.previous_attempts:
            failed_approaches = [attempt.get('approach', 'unknown') for attempt in context.previous_attempts]
            enhanced['failed_approaches'] = ', '.join(set(failed_approaches))
        
        return enhanced
    
    def _enhance_knowledge_context(self, context: PromptContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance context with retrieved knowledge."""
        if not context.knowledge_retrieved:
            return {'knowledge_context': 'No relevant knowledge retrieved'}
        
        # Format knowledge for prompt inclusion
        knowledge_items = []
        for knowledge in context.knowledge_retrieved[:3]:  # Top 3 most relevant
            knowledge_items.append(f"- {knowledge.get('type', 'Knowledge')}: {knowledge.get('application_guidance', 'No guidance')}")
        
        return {
            'knowledge_context': '\n'.join(knowledge_items),
            'knowledge_from_ledger': self._format_knowledge_summary(context.knowledge_retrieved)
        }
    
    def _enhance_domain_context(self, context: PromptContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance context with domain-specific information."""
        domain_info = data.get('domain_info', {})
        
        enhanced = {}
        
        # Add domain-specific requirements
        if context.domain in domain_info:
            domain_data = domain_info[context.domain]
            enhanced['requirements_context'] = self._format_domain_requirements(domain_data)
            enhanced['quality_standards'] = self._format_quality_standards(domain_data)
        
        # Add available tools formatted for the domain
        if context.available_tools:
            enhanced['available_tools'] = ', '.join(context.available_tools)
        
        return enhanced
    
    def _enhance_constraints_context(self, context: PromptContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance context with constraints information."""
        constraints = []
        
        if context.time_constraints:
            time_limit = context.time_constraints.get('limit_minutes', 'unknown')
            constraints.append(f"Time limit: {time_limit} minutes")
        
        if context.cost_constraints:
            budget = context.cost_constraints.get('budget', 'unknown')
            constraints.append(f"Budget limit: ${budget}")
        
        if context.constraints:
            for key, value in context.constraints.items():
                constraints.append(f"{key}: {value}")
        
        return {
            'constraints_context': '\n'.join(constraints) if constraints else 'No specific constraints',
            'budget_constraints': context.cost_constraints or {},
            'time_constraints': context.time_constraints or {}
        }
    
    def _enhance_history_context(self, context: PromptContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance context with historical information."""
        enhanced = {}
        
        # Previous stages
        stage_history = data.get('stage_history', [])
        if stage_history:
            enhanced['previous_stages'] = ', '.join(stage_history)
        
        # Decision history
        decision_history = data.get('decision_history', [])
        if decision_history:
            recent_decisions = [d.get('action', 'unknown') for d in decision_history[-3:]]
            enhanced['recent_decisions'] = ', '.join(recent_decisions)
        
        return enhanced
    
    def _format_error_classification(self, classification: Dict[str, Any]) -> str:
        """Format error classification for prompt inclusion."""
        if not classification:
            return "No error classification available"
        
        parts = []
        if 'category' in classification:
            parts.append(f"Category: {classification['category']}")
        if 'severity' in classification:
            parts.append(f"Severity: {classification['severity']}")
        if 'suggested_actions' in classification:
            actions = [action.get('action', 'unknown') for action in classification['suggested_actions'][:2]]
            parts.append(f"Suggested actions: {', '.join(actions)}")
        
        return '\n'.join(parts)
    
    def _format_knowledge_summary(self, knowledge_list: List[Dict[str, Any]]) -> str:
        """Format knowledge for strategic decision making."""
        if not knowledge_list:
            return "No historical knowledge available"
        
        summary_parts = []
        for knowledge in knowledge_list[:2]:  # Top 2 items
            knowledge_type = knowledge.get('type', 'Knowledge')
            confidence = knowledge.get('confidence', 0.0)
            summary_parts.append(f"- {knowledge_type} (confidence: {confidence:.1f}): {knowledge.get('content', {}).get('pattern', 'No details')}")
        
        return '\n'.join(summary_parts)
    
    def _format_domain_requirements(self, domain_data: Dict[str, Any]) -> str:
        """Format domain-specific requirements."""
        requirements = []
        
        if 'quality_gates' in domain_data:
            for gate, threshold in domain_data['quality_gates'].items():
                requirements.append(f"- {gate}: minimum {threshold}")
        
        if 'coding_standards' in domain_data:
            for standard in domain_data['coding_standards']:
                requirements.append(f"- Follow {standard}")
        
        return '\n'.join(requirements) if requirements else "Standard requirements apply"
    
    def _format_quality_standards(self, domain_data: Dict[str, Any]) -> str:
        """Format quality standards for the domain."""
        standards = []
        
        if 'test_coverage_min' in domain_data:
            standards.append(f"Test coverage: minimum {domain_data['test_coverage_min']}%")
        
        if 'code_quality_min' in domain_data:
            standards.append(f"Code quality score: minimum {domain_data['code_quality_min']}")
        
        return '\n'.join(standards) if standards else "Standard quality expectations"


class ResponseAnalyzer:
    """
    Analyzes Claude responses for quality, completeness, and extractable information.
    """
    
    def __init__(self):
        """Initialize response analyzer."""
        self.quality_metrics = {
            'completeness': self._assess_completeness,
            'accuracy': self._assess_accuracy,
            'clarity': self._assess_clarity,
            'actionability': self._assess_actionability,
            'format_compliance': self._assess_format_compliance
        }
    
    def analyze_response(self, 
                        response: str,
                        prompt_type: PromptType,
                        expected_format: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze Claude response for quality and extract structured information.
        
        Args:
            response: Claude's response text
            prompt_type: Type of prompt that generated this response
            expected_format: Expected response format (if any)
            
        Returns:
            Analysis results with quality scores and extracted data
        """
        analysis = {
            'response_length': len(response),
            'word_count': len(response.split()),
            'quality_scores': {},
            'extracted_data': {},
            'issues': [],
            'overall_quality': ResponseQuality.ADEQUATE,
            'confidence': 0.7
        }
        
        # Apply quality metrics
        total_score = 0.0
        for metric_name, metric_func in self.quality_metrics.items():
            try:
                score = metric_func(response, prompt_type, expected_format)
                analysis['quality_scores'][metric_name] = score
                total_score += score
            except Exception as e:
                logger.warning(f"Quality metric {metric_name} failed: {e}")
                analysis['quality_scores'][metric_name] = 0.5
                total_score += 0.5
        
        # Calculate overall quality
        average_score = total_score / len(self.quality_metrics)
        analysis['overall_quality'] = self._score_to_quality(average_score)
        analysis['confidence'] = average_score
        
        # Extract structured data based on prompt type
        analysis['extracted_data'] = self._extract_structured_data(response, prompt_type)
        
        # Identify issues
        analysis['issues'] = self._identify_issues(response, analysis['quality_scores'])
        
        return analysis
    
    def _assess_completeness(self, response: str, prompt_type: PromptType, expected_format: Optional[Dict]) -> float:
        """Assess completeness of the response."""
        # Basic completeness indicators
        indicators = {
            'has_substantive_content': len(response.strip()) > 50,
            'has_structured_sections': bool(re.search(r'\*\*[^*]+\*\*', response)),
            'addresses_multiple_points': response.count('\n') > 3,
            'has_examples_or_code': '```' in response or 'example' in response.lower(),
        }
        
        # Prompt-type specific completeness
        if prompt_type == PromptType.CODE_GENERATION:
            indicators['has_code_blocks'] = '```' in response
            indicators['has_documentation'] = any(word in response.lower() for word in ['usage', 'example', 'documentation'])
        
        elif prompt_type == PromptType.ERROR_ANALYSIS:
            indicators['has_root_cause'] = 'root cause' in response.lower()
            indicators['has_solution'] = any(word in response.lower() for word in ['solution', 'fix', 'resolve'])
        
        elif prompt_type == PromptType.DECISION_MAKING:
            indicators['has_recommendation'] = 'recommend' in response.lower()
            indicators['has_reasoning'] = any(word in response.lower() for word in ['because', 'reason', 'rationale'])
        
        return sum(indicators.values()) / len(indicators)
    
    def _assess_accuracy(self, response: str, prompt_type: PromptType, expected_format: Optional[Dict]) -> float:
        """Assess accuracy of the response (simplified heuristic)."""
        # This is a simplified accuracy assessment
        # In production, could use more sophisticated NLP techniques
        
        accuracy_indicators = {
            'no_contradictions': not self._has_contradictions(response),
            'technical_consistency': self._check_technical_consistency(response),
            'logical_flow': self._check_logical_flow(response),
        }
        
        # Format-specific accuracy
        if expected_format and 'json' in str(expected_format).lower():
            try:
                # Try to extract and parse JSON
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    json.loads(json_match.group(1))
                    accuracy_indicators['valid_json'] = True
                else:
                    accuracy_indicators['valid_json'] = False
            except:
                accuracy_indicators['valid_json'] = False
        
        return sum(accuracy_indicators.values()) / len(accuracy_indicators)
    
    def _assess_clarity(self, response: str, prompt_type: PromptType, expected_format: Optional[Dict]) -> float:
        """Assess clarity and readability of the response."""
        clarity_indicators = {
            'good_structure': bool(re.search(r'\*\*[^*]+\*\*', response)),
            'appropriate_length': 100 <= len(response) <= 5000,
            'clear_language': self._check_clear_language(response),
            'good_formatting': self._check_formatting(response),
        }
        
        return sum(clarity_indicators.values()) / len(clarity_indicators)
    
    def _assess_actionability(self, response: str, prompt_type: PromptType, expected_format: Optional[Dict]) -> float:
        """Assess how actionable the response is."""
        actionability_indicators = {
            'specific_steps': any(word in response.lower() for word in ['step', 'action', 'command', 'run']),
            'concrete_examples': '```' in response or 'example' in response.lower(),
            'clear_next_steps': any(phrase in response.lower() for phrase in ['next', 'then', 'after', 'following']),
        }
        
        # Prompt-specific actionability
        if prompt_type == PromptType.ERROR_ANALYSIS:
            actionability_indicators['provides_fix'] = any(word in response.lower() for word in ['fix', 'solution', 'resolve'])
        
        elif prompt_type == PromptType.CODE_GENERATION:
            actionability_indicators['runnable_code'] = '```' in response
        
        return sum(actionability_indicators.values()) / len(actionability_indicators)
    
    def _assess_format_compliance(self, response: str, prompt_type: PromptType, expected_format: Optional[Dict]) -> float:
        """Assess compliance with expected format."""
        if not expected_format:
            return 1.0  # No format requirements
        
        compliance_score = 1.0
        
        # Check for required sections
        if 'sections' in expected_format:
            for section in expected_format['sections']:
                if section.lower() not in response.lower():
                    compliance_score -= 0.2
        
        # Check for JSON format if required
        if expected_format.get('format') == 'json':
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if not json_match:
                compliance_score -= 0.5
        
        return max(0.0, compliance_score)
    
    def _extract_structured_data(self, response: str, prompt_type: PromptType) -> Dict[str, Any]:
        """Extract structured data from response based on prompt type."""
        extracted = {}
        
        # Extract JSON if present
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                extracted['json_data'] = json.loads(json_match.group(1))
            except:
                extracted['json_data'] = None
        
        # Extract code blocks
        code_blocks = re.findall(r'```(?:python|javascript|bash|sql)?\s*\n(.*?)\n```', response, re.DOTALL)
        if code_blocks:
            extracted['code_blocks'] = code_blocks
        
        # Extract lists and action items
        action_items = re.findall(r'^\s*[-*]\s*(.+)$', response, re.MULTILINE)
        if action_items:
            extracted['action_items'] = action_items
        
        # Prompt-specific extraction
        if prompt_type == PromptType.DECISION_MAKING:
            # Extract recommendation
            rec_match = re.search(r'recommend(?:ed|ation)?[:\s]+([^.\n]+)', response, re.IGNORECASE)
            if rec_match:
                extracted['recommendation'] = rec_match.group(1).strip()
        
        elif prompt_type == PromptType.ERROR_ANALYSIS:
            # Extract root cause
            cause_match = re.search(r'root cause[:\s]+([^.\n]+)', response, re.IGNORECASE)
            if cause_match:
                extracted['root_cause'] = cause_match.group(1).strip()
        
        return extracted
    
    def _score_to_quality(self, score: float) -> ResponseQuality:
        """Convert numeric score to quality enum."""
        if score >= 0.9:
            return ResponseQuality.EXCELLENT
        elif score >= 0.75:
            return ResponseQuality.GOOD
        elif score >= 0.6:
            return ResponseQuality.ADEQUATE
        elif score >= 0.4:
            return ResponseQuality.POOR
        else:
            return ResponseQuality.UNUSABLE
    
    def _has_contradictions(self, response: str) -> bool:
        """Check for obvious contradictions (simplified)."""
        # Look for contradictory words in close proximity
        contradiction_patterns = [
            (r'\b(yes|true|correct)\b.*?\b(no|false|incorrect)\b', 50),
            (r'\b(recommended|should)\b.*?\b(not recommended|should not)\b', 100),
            (r'\b(safe|secure)\b.*?\b(unsafe|insecure)\b', 50),
        ]
        
        for pattern, max_distance in contradiction_patterns:
            matches = list(re.finditer(pattern, response, re.IGNORECASE))
            for match in matches:
                if len(match.group(0)) <= max_distance:
                    return True
        
        return False
    
    def _check_technical_consistency(self, response: str) -> bool:
        """Check for technical consistency (simplified)."""
        # Check for consistent terminology
        # This is a simplified check - production would be more sophisticated
        
        # Look for consistent naming conventions
        if 'camelCase' in response and 'snake_case' in response:
            # Mixed naming conventions might indicate inconsistency
            return False
        
        return True
    
    def _check_logical_flow(self, response: str) -> bool:
        """Check for logical flow in the response."""
        # Simple check for transition words and logical structure
        transition_words = ['first', 'then', 'next', 'finally', 'because', 'therefore', 'however']
        transition_count = sum(1 for word in transition_words if word in response.lower())
        
        # Responses should have some logical flow indicators
        return transition_count >= 2
    
    def _check_clear_language(self, response: str) -> bool:
        """Check for clear, understandable language."""
        # Simple heuristics for clarity
        sentences = response.split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        
        # Sentences should be reasonably short
        return avg_sentence_length <= 25
    
    def _check_formatting(self, response: str) -> bool:
        """Check for good formatting."""
        formatting_indicators = [
            bool(re.search(r'\*\*[^*]+\*\*', response)),  # Bold headers
            '\n\n' in response,  # Paragraph breaks
            response.count('\n') > 2,  # Multiple lines
        ]
        
        return sum(formatting_indicators) >= 2
    
    def _identify_issues(self, response: str, quality_scores: Dict[str, float]) -> List[str]:
        """Identify specific issues with the response."""
        issues = []
        
        # Check quality scores for problems
        for metric, score in quality_scores.items():
            if score < 0.5:
                issues.append(f"Low {metric} score ({score:.2f})")
        
        # Check for specific problems
        if len(response) < 50:
            issues.append("Response too short")
        
        if len(response) > 10000:
            issues.append("Response too long")
        
        if not re.search(r'[.!?]', response):
            issues.append("No proper sentence structure")
        
        return issues


class PromptOrchestrator:
    """
    Main orchestrator that manages prompt construction, execution, and optimization.
    """
    
    def __init__(self, 
                 claude_client: Any,
                 templates_path: Optional[Path] = None,
                 persistence_path: Optional[Path] = None):
        """
        Initialize prompt orchestrator.
        
        Args:
            claude_client: Client for Claude API
            templates_path: Path to custom template files
            persistence_path: Path for storing execution history and optimizations
        """
        self.claude_client = claude_client
        self.persistence_path = persistence_path or Path("./prompt_orchestration")
        self.persistence_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.template_library = PromptTemplateLibrary(templates_path)
        self.context_enhancer = ContextEnhancer()
        self.response_analyzer = ResponseAnalyzer()
        
        # Execution tracking
        self.execution_history: List[PromptExecution] = []
        self.template_performance: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            'total_executions': 0,
            'average_quality': 0.0,
            'success_rate': 0.0,
            'average_cost': 0.0,
            'average_time': 0.0
        })
        
        # Load historical data
        self._load_execution_history()
        
        logger.info("PromptOrchestrator initialized")
    
    async def execute_prompt(self,
                           prompt_type: PromptType,
                           context: PromptContext,
                           available_data: Optional[Dict[str, Any]] = None,
                           template_id: Optional[str] = None) -> PromptExecution:
        """
        Execute a prompt with optimal template and context.
        
        Args:
            prompt_type: Type of prompt to execute
            context: Base context for the prompt
            available_data: Additional data for context enhancement
            template_id: Specific template to use (optional)
            
        Returns:
            PromptExecution with results and analysis
        """
        start_time = datetime.now()
        
        # Select template
        if template_id:
            template = self.template_library.get_template(template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
        else:
            template = self.template_library.find_best_template(prompt_type, context)
            if not template:
                raise ValueError(f"No suitable template found for {prompt_type}")
        
        # Enhance context
        available_data = available_data or {}
        enhanced_context = self.context_enhancer.enhance_context(context, available_data)
        
        # Render prompt
        try:
            rendered_prompt = template.render(enhanced_context)
        except Exception as e:
            logger.error(f"Failed to render template {template.template_id}: {e}")
            raise
        
        # Execute with Claude
        response, token_usage, cost = await self._execute_with_claude(rendered_prompt)
        
        # Analyze response
        expected_format = self._get_expected_format(template)
        analysis = self.response_analyzer.analyze_response(response, prompt_type, expected_format)
        
        # Create execution record
        execution_time = (datetime.now() - start_time).total_seconds()
        execution = PromptExecution(
            execution_id=self._generate_execution_id(),
            template_id=template.template_id,
            rendered_prompt=rendered_prompt,
            context=context,
            response=response,
            response_quality=analysis['overall_quality'],
            execution_time=execution_time,
            token_usage=token_usage,
            cost=cost,
            success_indicators=analysis['quality_scores'],
            failure_indicators={issue: 1.0 for issue in analysis['issues']},
            metadata={
                'analysis': analysis,
                'enhanced_context_keys': list(enhanced_context.keys())
            }
        )
        
        # Record execution
        self._record_execution(execution, template)
        
        logger.info(f"Executed prompt {template.template_id} with quality {analysis['overall_quality'].name}")
        
        return execution
    
    async def _execute_with_claude(self, prompt: str) -> Tuple[str, Dict[str, int], float]:
        """Execute prompt with Claude and return response, token usage, and cost."""
        try:
            # This would integrate with your actual Claude client
            response = await self.claude_client.chat(prompt, max_tokens=4000)
            
            # Extract token usage and cost (these would come from the actual client)
            token_usage = {
                'prompt_tokens': len(prompt.split()) * 1.3,  # Rough estimate
                'response_tokens': len(response.content.split()) * 1.3,
                'total_tokens': len(prompt.split()) * 1.3 + len(response.content.split()) * 1.3
            }
            
            # Estimate cost (this would be provided by the client)
            cost = token_usage['total_tokens'] * 0.00001  # Rough estimate
            
            return response.content, token_usage, cost
            
        except Exception as e:
            logger.error(f"Claude execution failed: {e}")
            raise
    
    def _record_execution(self, execution: PromptExecution, template: PromptTemplate):
        """Record execution for performance tracking and optimization."""
        self.execution_history.append(execution)
        
        # Update template performance metrics
        perf = self.template_performance[template.template_id]
        perf['total_executions'] += 1
        
        # Update averages using exponential moving average
        alpha = 0.1  # Learning rate
        quality_score = self._quality_to_score(execution.response_quality)
        
        if perf['total_executions'] == 1:
            perf['average_quality'] = quality_score
            perf['average_cost'] = execution.cost
            perf['average_time'] = execution.execution_time
        else:
            perf['average_quality'] = (1 - alpha) * perf['average_quality'] + alpha * quality_score
            perf['average_cost'] = (1 - alpha) * perf['average_cost'] + alpha * execution.cost
            perf['average_time'] = (1 - alpha) * perf['average_time'] + alpha * execution.execution_time
        
        # Update success rate
        is_success = execution.response_quality in [ResponseQuality.EXCELLENT, ResponseQuality.GOOD]
        if perf['total_executions'] == 1:
            perf['success_rate'] = 1.0 if is_success else 0.0
        else:
            perf['success_rate'] = (1 - alpha) * perf['success_rate'] + alpha * (1.0 if is_success else 0.0)
        
        # Update template success metrics
        template.success_metrics = {
            'average_quality': perf['average_quality'],
            'success_rate': perf['success_rate'],
            'total_executions': perf['total_executions']
        }
        
        # Periodically save history
        if len(self.execution_history) % 10 == 0:
            self._save_execution_history()
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get recommendations for optimizing prompt performance."""
        recommendations = []
        
        # Analyze template performance
        for template_id, perf in self.template_performance.items():
            if perf['total_executions'] >= 5:  # Only analyze templates with sufficient data
                
                # Low success rate templates
                if perf['success_rate'] < 0.7:
                    recommendations.append({
                        'type': 'template_improvement',
                        'template_id': template_id,
                        'issue': 'low_success_rate',
                        'current_rate': perf['success_rate'],
                        'suggestion': 'Review and revise template structure and instructions'
                    })
                
                # High cost templates
                if perf['average_cost'] > 0.1:  # Threshold for high cost
                    recommendations.append({
                        'type': 'cost_optimization',
                        'template_id': template_id,
                        'issue': 'high_cost',
                        'current_cost': perf['average_cost'],
                        'suggestion': 'Reduce prompt length or optimize for efficiency'
                    })
        
        # Analyze common failure patterns
        recent_failures = [e for e in self.execution_history[-50:] 
                          if e.response_quality in [ResponseQuality.POOR, ResponseQuality.UNUSABLE]]
        
        if len(recent_failures) > 5:
            failure_patterns = self._analyze_failure_patterns(recent_failures)
            for pattern in failure_patterns:
                recommendations.append({
                    'type': 'pattern_fix',
                    'pattern': pattern,
                    'suggestion': 'Address common failure pattern across templates'
                })
        
        return recommendations
    
    def optimize_template(self, template_id: str, feedback: Dict[str, Any]) -> PromptTemplate:
        """Optimize a template based on performance feedback."""
        template = self.template_library.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Create optimized version
        optimized_template = PromptTemplate(
            template_id=f"{template_id}_optimized_{datetime.now().strftime('%Y%m%d')}",
            prompt_type=template.prompt_type,
            template_text=template.template_text,
            required_variables=template.required_variables.copy(),
            optional_variables=template.optional_variables.copy(),
            version=f"{template.version}_opt"
        )
        
        # Apply optimizations based on feedback
        if feedback.get('add_structure'):
            optimized_template.template_text = self._add_structure_to_template(optimized_template.template_text)
        
        if feedback.get('reduce_length'):
            optimized_template.template_text = self._reduce_template_length(optimized_template.template_text)
        
        if feedback.get('improve_clarity'):
            optimized_template.template_text = self._improve_template_clarity(optimized_template.template_text)
        
        # Add to library
        self.template_library.add_template(optimized_template)
        
        return optimized_template
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get comprehensive execution statistics."""
        if not self.execution_history:
            return {'total_executions': 0}
        
        recent_executions = self.execution_history[-100:]  # Last 100 executions
        
        # Quality distribution
        quality_counts = {}
        for quality in ResponseQuality:
            quality_counts[quality.name] = sum(1 for e in recent_executions if e.response_quality == quality)
        
        # Average metrics
        avg_cost = sum(e.cost for e in recent_executions) / len(recent_executions)
        avg_time = sum(e.execution_time for e in recent_executions) / len(recent_executions)
        avg_tokens = sum(e.token_usage.get('total_tokens', 0) for e in recent_executions) / len(recent_executions)
        
        # Template performance
        template_stats = {}
        for template_id, perf in self.template_performance.items():
            if perf['total_executions'] > 0:
                template_stats[template_id] = {
                    'executions': perf['total_executions'],
                    'success_rate': perf['success_rate'],
                    'average_quality': perf['average_quality']
                }
        
        return {
            'total_executions': len(self.execution_history),
            'recent_executions': len(recent_executions),
            'quality_distribution': quality_counts,
            'average_cost': avg_cost,
            'average_execution_time': avg_time,
            'average_tokens': avg_tokens,
            'template_performance': template_stats,
            'success_rate': sum(1 for e in recent_executions 
                              if e.response_quality in [ResponseQuality.EXCELLENT, ResponseQuality.GOOD]) / len(recent_executions)
        }
    
    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        counter = len(self.execution_history)
        return f"exec_{timestamp}_{counter:04d}"
    
    def _get_expected_format(self, template: PromptTemplate) -> Optional[Dict[str, Any]]:
        """Extract expected response format from template."""
        if 'json' in template.template_text.lower():
            return {'format': 'json'}
        
        # Look for specific sections mentioned in template
        sections = re.findall(r'\*\*([^*]+)\*\*', template.template_text)
        if sections:
            return {'sections': sections}
        
        return None
    
    def _quality_to_score(self, quality: ResponseQuality) -> float:
        """Convert quality enum to numeric score."""
        quality_scores = {
            ResponseQuality.EXCELLENT: 1.0,
            ResponseQuality.GOOD: 0.8,
            ResponseQuality.ADEQUATE: 0.6,
            ResponseQuality.POOR: 0.4,
            ResponseQuality.UNUSABLE: 0.2
        }
        return quality_scores.get(quality, 0.5)
    
    def _analyze_failure_patterns(self, failures: List[PromptExecution]) -> List[str]:
        """Analyze common patterns in failures."""
        patterns = []
        
        # Common failure indicators
        failure_indicators = defaultdict(int)
        for failure in failures:
            for indicator in failure.failure_indicators.keys():
                failure_indicators[indicator] += 1
        
        # Identify patterns that occur in > 50% of failures
        threshold = len(failures) * 0.5
        for indicator, count in failure_indicators.items():
            if count > threshold:
                patterns.append(indicator)
        
        return patterns
    
    def _add_structure_to_template(self, template_text: str) -> str:
        """Add more structure to template."""
        # Simple optimization - add more section headers
        if '**' not in template_text:
            # Add basic structure
            lines = template_text.split('\n')
            structured_lines = ['**TASK OVERVIEW**:', lines[0], '', '**INSTRUCTIONS**:'] + lines[1:]
            return '\n'.join(structured_lines)
        
        return template_text
    
    def _reduce_template_length(self, template_text: str) -> str:
        """Reduce template length while preserving key information."""
        # Simple optimization - remove some verbose explanations
        lines = template_text.split('\n')
        reduced_lines = []
        
        for line in lines:
            # Skip overly verbose lines
            if len(line) > 200 and not any(marker in line for marker in ['$', '**', '```']):
                # Truncate long lines that don't contain variables or formatting
                reduced_lines.append(line[:150] + '...')
            else:
                reduced_lines.append(line)
        
        return '\n'.join(reduced_lines)
    
    def _improve_template_clarity(self, template_text: str) -> str:
        """Improve template clarity."""
        # Simple optimization - ensure clear section breaks
        improved = template_text.replace('\n\n\n', '\n\n')  # Normalize spacing
        
        # Ensure clear output format section
        if 'OUTPUT FORMAT' not in improved and 'output' in improved.lower():
            improved = improved.replace('output:', '**OUTPUT FORMAT**:')
        
        return improved
    
    def _save_execution_history(self):
        """Save execution history to disk."""
        history_file = self.persistence_path / "execution_history.pkl"
        performance_file = self.persistence_path / "template_performance.pkl"
        
        try:
            with open(history_file, 'wb') as f:
                # Only save recent history to manage file size
                recent_history = self.execution_history[-1000:]  # Last 1000 executions
                pickle.dump(recent_history, f)
            
            with open(performance_file, 'wb') as f:
                pickle.dump(dict(self.template_performance), f)
                
            logger.info(f"Saved execution history ({len(self.execution_history)} executions)")
            
        except Exception as e:
            logger.error(f"Failed to save execution history: {e}")
    
    def _load_execution_history(self):
        """Load execution history from disk."""
        history_file = self.persistence_path / "execution_history.pkl"
        performance_file = self.persistence_path / "template_performance.pkl"
        
        try:
            if history_file.exists():
                with open(history_file, 'rb') as f:
                    self.execution_history = pickle.load(f)
            
            if performance_file.exists():
                with open(performance_file, 'rb') as f:
                    loaded_performance = pickle.load(f)
                    self.template_performance.update(loaded_performance)
            
            logger.info(f"Loaded execution history ({len(self.execution_history)} executions)")
            
        except Exception as e:
            logger.warning(f"Failed to load execution history: {e}")


# Example usage and testing
if __name__ == "__main__":
    import tempfile
    import asyncio
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Mock Claude client for testing
    class MockClaudeClient:
        async def chat(self, prompt: str, max_tokens: int = 4000):
            from types import SimpleNamespace
            
            # Generate different responses based on prompt content
            if 'error' in prompt.lower():
                content = """
                **ROOT CAUSE**: ModuleNotFoundError indicates a missing Python package

                **IMMEDIATE CAUSE**: The 'requests' module is not installed in the current environment

                **SOLUTION STRATEGY**: Install the missing package using pip

                **RECOMMENDED ACTIONS**:
                ```json
                {
                  "root_cause": "Missing requests package",
                  "immediate_cause": "Import statement failed",
                  "solution_strategy": "Install package via pip",
                  "recommended_actions": [
                    {
                      "action": "install_package",
                      "command": "pip install requests",
                      "reasoning": "Direct installation of missing dependency",
                      "confidence": 0.95
                    }
                  ],
                  "confidence_level": 0.9
                }
                ```
                """
            elif 'code' in prompt.lower():
                content = """
                **IMPLEMENTATION**:
                ```python
                import requests

                def fetch_data(url):
                    try:
                        response = requests.get(url)
                        response.raise_for_status()
                        return response.json()
                    except requests.RequestException as e:
                        print(f"Error fetching data: {e}")
                        return None

                # Usage example
                data = fetch_data("https://api.example.com/data")
                ```

                **TESTING**: Run the function with a test URL to verify functionality

                **DOCUMENTATION**: This function fetches JSON data from a URL with error handling
                """
            else:
                content = """
                This is a comprehensive response to your request. The solution involves multiple steps and considerations that need to be carefully implemented.

                **KEY POINTS**:
                - Approach is technically sound
                - Implementation should be straightforwar