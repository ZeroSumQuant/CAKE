#!/usr/bin/env python3
"""
rule_creator.py - Intelligent Rule Generation for CAKE

Enables Claude to propose automation rules from failure patterns,
with comprehensive validation and safety checks.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import re
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import hashlib
import ast

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class RuleProposal:
    """
    Represents a proposed automation rule.
    
    Attributes:
        signature: Unique identifier for the rule pattern
        check_expression: Python expression to match errors
        fix_command: Shell command to fix the issue
        confidence: 0.0-1.0 confidence in the rule
        explanation: Human-readable explanation
        test_cases: Example cases this rule would match
        safety_score: 0.0-1.0 safety rating
        estimated_impact: Predicted impact metrics
    """
    signature: str
    check_expression: str
    fix_command: str
    confidence: float
    explanation: str
    test_cases: List[Dict[str, str]] = field(default_factory=list)
    safety_score: float = 1.0
    estimated_impact: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def to_rule_format(self) -> Dict[str, Any]:
        """Convert to standard rule engine format."""
        return {
            'signature': self.signature,
            'check': self.check_expression,
            'autofix': self.fix_command,
            'confidence': self.confidence,
            'created': datetime.now().isoformat(),
            'test_cases': self.test_cases,
            'safety_score': self.safety_score
        }


class RuleValidator:
    """
    Validates proposed rules for safety and correctness.
    """
    
    # Dangerous patterns in expressions
    DANGEROUS_EXPR_PATTERNS = [
        r'__[a-zA-Z]+__',  # Dunder methods
        r'eval\s*\(',       # eval calls
        r'exec\s*\(',       # exec calls
        r'import\s+',       # import statements
        r'open\s*\(',       # file operations
        r'subprocess',      # subprocess calls
        r'os\.',           # os module access
        r'sys\.',          # sys module access
    ]
    
    # Dangerous patterns in commands
    DANGEROUS_CMD_PATTERNS = [
        r'rm\s+-rf\s+/',           # Dangerous deletions
        r'>\s*/dev/[^n]',          # Overwriting devices
        r'dd\s+if=',               # Disk operations
        r'mkfs',                   # Filesystem creation
        r'fdisk',                  # Disk partitioning
        r'curl.*\|\s*sh',          # Curl pipe to shell
        r'wget.*\|\s*bash',        # Wget pipe to bash
        r'chmod\s+777',            # Overly permissive
        r'chown\s+.*:.*\s+/',      # Changing root ownership
        r'sudo\s+',                # Sudo commands
        r'.*\$\(.*\)',             # Command substitution
        r'.*`.*`',                 # Backtick substitution
    ]
    
    # Whitelisted command prefixes
    SAFE_COMMANDS = {
        'pip install',
        'pip uninstall',
        'pytest',
        'python -m',
        'git add',
        'git commit',
        'git push',
        'git pull',
        'echo',
        'mkdir -p',
        'touch',
        'chmod +x',
        'flake8',
        'black',
        'mypy',
    }
    
    def __init__(self):
        """Initialize validator with compiled patterns."""
        self.expr_patterns = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_EXPR_PATTERNS]
        self.cmd_patterns = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_CMD_PATTERNS]
    
    def validate_proposal(self, proposal: RuleProposal) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation of a rule proposal.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Validate expression
        expr_issues = self.validate_expression(proposal.check_expression)
        issues.extend(expr_issues)
        
        # Validate command
        cmd_issues = self.validate_command(proposal.fix_command)
        issues.extend(cmd_issues)
        
        # Validate confidence
        if proposal.confidence < 0.0 or proposal.confidence > 1.0:
            issues.append(f"Invalid confidence: {proposal.confidence}")
        
        # Validate safety score
        if proposal.safety_score < 0.5:
            issues.append(f"Low safety score: {proposal.safety_score}")
        
        # Check if explanation is meaningful
        if len(proposal.explanation) < 10:
            issues.append("Explanation too short")
        
        return len(issues) == 0, issues
    
    def validate_expression(self, expression: str) -> List[str]:
        """Validate check expression for safety."""
        issues = []
        
        # Check for dangerous patterns
        for pattern in self.expr_patterns:
            if pattern.search(expression):
                issues.append(f"Dangerous pattern in expression: {pattern.pattern}")
        
        # Try to parse as AST
        try:
            tree = ast.parse(expression, mode='eval')
            
            # Check for forbidden node types
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    issues.append("Import statements not allowed")
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec', 'compile']:
                        issues.append(f"Forbidden function: {node.func.id}")
            
        except SyntaxError as e:
            issues.append(f"Invalid Python expression: {e}")
        
        # Check complexity (prevent overly complex expressions)
        if len(expression) > 200:
            issues.append("Expression too complex (> 200 chars)")
        
        return issues
    
    def validate_command(self, command: str) -> List[str]:
        """Validate fix command for safety."""
        issues = []
        
        # Check for dangerous patterns
        for pattern in self.cmd_patterns:
            if pattern.search(command):
                issues.append(f"Dangerous command pattern: {pattern.pattern}")
        
        # Check if command starts with safe prefix
        is_safe = any(command.strip().startswith(safe) for safe in self.SAFE_COMMANDS)
        if not is_safe:
            # Check individual command
            first_word = command.strip().split()[0] if command.strip() else ""
            if first_word not in ['pip', 'pytest', 'python', 'git', 'echo', 'mkdir', 'touch', 'chmod', 'flake8', 'black', 'mypy']:
                issues.append(f"Command not in whitelist: {first_word}")
        
        # Check for shell metacharacters that could be dangerous
        dangerous_chars = ['$', '`', ';', '&&', '||', '|', '>', '<', '*', '?', '[', ']']
        for char in dangerous_chars:
            if char in command and char not in ['|', '>', '*']:  # Some are ok in specific contexts
                issues.append(f"Potentially dangerous character: {char}")
        
        # Length check
        if len(command) > 500:
            issues.append("Command too long (> 500 chars)")
        
        return issues
    
    def calculate_safety_score(self, proposal: RuleProposal) -> float:
        """
        Calculate overall safety score for a proposal.
        
        Returns:
            Score from 0.0 (dangerous) to 1.0 (safe)
        """
        score = 1.0
        
        # Penalize for validation issues
        _, issues = self.validate_proposal(proposal)
        score -= len(issues) * 0.1
        
        # Bonus for simple, clear commands
        if proposal.fix_command.startswith(('pip install', 'echo', 'mkdir')):
            score += 0.1
        
        # Penalize for complex expressions
        if len(proposal.check_expression) > 100:
            score -= 0.1
        
        # Penalize for low confidence
        if proposal.confidence < 0.7:
            score -= 0.2
        
        return max(0.0, min(1.0, score))


class RuleCreator:
    """
    Creates intelligent rule proposals from failure patterns.
    """
    
    def __init__(self, claude_client: Any, validator: Optional[RuleValidator] = None):
        """
        Initialize rule creator.
        
        Args:
            claude_client: Client for Claude API calls
            validator: Rule validator (creates default if not provided)
        """
        self.client = claude_client
        self.validator = validator or RuleValidator()
        self.proposal_cache: Dict[str, RuleProposal] = {}
        self.pattern_library = self._load_pattern_library()
        
        logger.info("RuleCreator initialized")
    
    def _load_pattern_library(self) -> Dict[str, Dict[str, Any]]:
        """Load library of common patterns and fixes."""
        return {
            'ModuleNotFoundError': {
                'pattern': r"ModuleNotFoundError.*'([^']+)'",
                'fix_template': "pip install {module}",
                'confidence': 0.9,
                'explanation': "Missing Python module that can be installed via pip"
            },
            'PermissionError': {
                'pattern': r"Permission denied.*'([^']+)'",
                'fix_template': "chmod +x {file}",
                'confidence': 0.8,
                'explanation': "File permissions need to be updated"
            },
            'FileNotFoundError': {
                'pattern': r"FileNotFoundError.*'([^']+)'",
                'fix_template': "touch {file}",
                'confidence': 0.7,
                'explanation': "Required file is missing"
            },
            'AssertionError': {
                'pattern': r"AssertionError:\s*(.+)",
                'fix_template': None,  # No generic fix
                'confidence': 0.5,
                'explanation': "Test assertion failed - requires code changes"
            },
            'ConnectionError': {
                'pattern': r"(Connection|Timeout).*to\s+(\S+)",
                'fix_template': None,  # No generic fix
                'confidence': 0.6,
                'explanation': "Network connection issue"
            }
        }
    
    async def propose_rule(self, stage: str, error: str, context: Dict[str, Any]) -> Optional[RuleProposal]:
        """
        Generate rule proposal from failure pattern.
        
        Args:
            stage: TRRDEVS stage where failure occurred
            error: Error message
            context: Additional context (previous attempts, etc)
            
        Returns:
            RuleProposal if successful, None otherwise
        """
        # Check cache first
        cache_key = self._generate_cache_key(stage, error)
        if cache_key in self.proposal_cache:
            logger.info("Returning cached proposal")
            return self.proposal_cache[cache_key]
        
        # Try pattern matching first
        pattern_proposal = self._try_pattern_matching(stage, error)
        if pattern_proposal:
            # Enhance with Claude if available
            enhanced = await self._enhance_with_claude(pattern_proposal, context)
            if enhanced:
                pattern_proposal = enhanced
            
            # Validate and cache
            if self._validate_and_finalize(pattern_proposal):
                self.proposal_cache[cache_key] = pattern_proposal
                return pattern_proposal
        
        # Fall back to full Claude generation
        claude_proposal = await self._generate_with_claude(stage, error, context)
        if claude_proposal and self._validate_and_finalize(claude_proposal):
            self.proposal_cache[cache_key] = claude_proposal
            return claude_proposal
        
        logger.warning(f"Failed to generate valid proposal for {stage}:{error[:50]}")
        return None
    
    def _try_pattern_matching(self, stage: str, error: str) -> Optional[RuleProposal]:
        """Try to match error against known patterns."""
        for error_type, pattern_config in self.pattern_library.items():
            pattern = re.compile(pattern_config['pattern'], re.IGNORECASE)
            match = pattern.search(error)
            
            if match:
                # Generate signature
                signature = self._generate_signature(stage, error_type, match.group(0))
                
                # Create check expression
                check_expr = f"stage == '{stage}' and '{error_type}' in error"
                if match.groups():
                    # Add specific match for first capture group
                    check_expr += f" and '{match.group(1)}' in error"
                
                # Generate fix command
                fix_cmd = None
                if pattern_config['fix_template'] and match.groups():
                    try:
                        # Safe string formatting
                        fix_cmd = pattern_config['fix_template'].format(
                            module=match.group(1),
                            file=match.group(1)
                        )
                    except:
                        fix_cmd = pattern_config['fix_template']
                
                if not fix_cmd:
                    # No automated fix available
                    continue
                
                # Create proposal
                proposal = RuleProposal(
                    signature=signature,
                    check_expression=check_expr,
                    fix_command=fix_cmd,
                    confidence=pattern_config['confidence'],
                    explanation=pattern_config['explanation'],
                    test_cases=[{
                        'stage': stage,
                        'error': error,
                        'should_match': True
                    }]
                )
                
                # Calculate safety score
                proposal.safety_score = self.validator.calculate_safety_score(proposal)
                
                return proposal
        
        return None
    
    async def _generate_with_claude(self, stage: str, error: str, context: Dict[str, Any]) -> Optional[RuleProposal]:
        """Generate proposal using Claude."""
        prompt = self._build_generation_prompt(stage, error, context)
        
        try:
            response = await self.client.chat(prompt, max_tokens=800)
            proposal = self._parse_claude_response(response.content, stage, error)
            return proposal
        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            return None
    
    async def _enhance_with_claude(self, proposal: RuleProposal, context: Dict[str, Any]) -> Optional[RuleProposal]:
        """Enhance pattern-matched proposal with Claude insights."""
        prompt = f"""
        I have a draft automation rule. Please review and enhance it:
        
        Current Rule:
        - Check: {proposal.check_expression}
        - Fix: {proposal.fix_command}
        - Explanation: {proposal.explanation}
        
        Context:
        {json.dumps(context, indent=2)}
        
        Please suggest:
        1. A more precise check expression if possible
        2. Additional test cases
        3. Potential edge cases or warnings
        
        Format your response as:
        CHECK: <improved expression or "KEEP">
        TEST_CASE: <stage>, <error example>, <should_match: true/false>
        WARNING: <any warnings or None>
        """
        
        try:
            response = await self.client.chat(prompt, max_tokens=500)
            
            # Parse enhancements
            content = response.content
            
            # Update check if improved
            if match := re.search(r'CHECK:\s*(.+)', content):
                new_check = match.group(1).strip()
                if new_check != "KEEP" and len(new_check) < 200:
                    proposal.check_expression = new_check
            
            # Add test cases
            for match in re.finditer(r'TEST_CASE:\s*([^,]+),\s*([^,]+),\s*(true|false)', content):
                proposal.test_cases.append({
                    'stage': match.group(1).strip(),
                    'error': match.group(2).strip(),
                    'should_match': match.group(3).lower() == 'true'
                })
            
            # Add warnings to metadata
            if match := re.search(r'WARNING:\s*(.+)', content):
                warning = match.group(1).strip()
                if warning.lower() != 'none':
                    proposal.metadata['warnings'] = proposal.metadata.get('warnings', [])
                    proposal.metadata['warnings'].append(warning)
            
            return proposal
            
        except Exception as e:
            logger.warning(f"Enhancement failed: {e}")
            return proposal
    
    def _build_generation_prompt(self, stage: str, error: str, context: Dict[str, Any]) -> str:
        """Build prompt for Claude rule generation."""
        # Get safe commands list
        safe_commands = '\n'.join(f"- {cmd}" for cmd in self.validator.SAFE_COMMANDS)
        
        return f"""
        Analyze this recurring failure and propose an automation rule.
        
        Failure Information:
        - Stage: {stage}
        - Error: {error}
        - Previous Attempts: {context.get('failure_count', 1)}
        - Previous Fixes Tried: {json.dumps(context.get('previous_fixes', []))}
        
        Generate a rule with:
        1. A Python expression to detect this error pattern
        2. A shell command to fix it automatically
        3. Your confidence level (0.0-1.0)
        4. A clear explanation
        
        Requirements:
        - The check expression must use only 'stage' and 'error' variables
        - The fix command must start with one of these safe commands:
        {safe_commands}
        - Be conservative - only suggest fixes you're confident will work
        - Consider side effects and safety
        
        Format your response EXACTLY as:
        SIGNATURE: <unique identifier>
        CHECK: <python expression>
        FIX: <shell command>
        CONFIDENCE: <float between 0 and 1>
        EXPLANATION: <one line explanation>
        TEST_CASE: <example error that should match>
        SAFETY_NOTES: <any safety concerns>
        
        Example:
        SIGNATURE: execute:ModuleNotFoundError:requests
        CHECK: stage == 'execute' and 'ModuleNotFoundError' in error and 'requests' in error
        FIX: pip install requests
        CONFIDENCE: 0.9
        EXPLANATION: Install missing requests module via pip
        TEST_CASE: ModuleNotFoundError: No module named 'requests'
        SAFETY_NOTES: Safe - only installs a specific package
        """
    
    def _parse_claude_response(self, content: str, stage: str, error: str) -> Optional[RuleProposal]:
        """Parse Claude's response into RuleProposal."""
        try:
            # Extract fields
            fields = {}
            
            # Required fields
            patterns = {
                'signature': r'SIGNATURE:\s*(.+)',
                'check': r'CHECK:\s*(.+)',
                'fix': r'FIX:\s*(.+)',
                'confidence': r'CONFIDENCE:\s*(\d*\.?\d+)',
                'explanation': r'EXPLANATION:\s*(.+)'
            }
            
            for field, pattern in patterns.items():
                match = re.search(pattern, content, re.MULTILINE)
                if match:
                    fields[field] = match.group(1).strip()
                else:
                    logger.warning(f"Missing required field: {field}")
                    return None
            
            # Optional fields
            test_case_match = re.search(r'TEST_CASE:\s*(.+)', content)
            safety_notes_match = re.search(r'SAFETY_NOTES:\s*(.+)', content)
            
            # Create proposal
            proposal = RuleProposal(
                signature=fields['signature'],
                check_expression=fields['check'],
                fix_command=fields['fix'],
                confidence=float(fields['confidence']),
                explanation=fields['explanation'],
                test_cases=[{
                    'stage': stage,
                    'error': test_case_match.group(1).strip() if test_case_match else error,
                    'should_match': True
                }]
            )
            
            # Add safety notes to metadata
            if safety_notes_match:
                proposal.metadata['safety_notes'] = safety_notes_match.group(1).strip()
            
            # Calculate safety score
            proposal.safety_score = self.validator.calculate_safety_score(proposal)
            
            return proposal
            
        except Exception as e:
            logger.error(f"Failed to parse Claude response: {e}")
            logger.debug(f"Response content: {content}")
            return None
    
    def _validate_and_finalize(self, proposal: RuleProposal) -> bool:
        """Validate and finalize a proposal."""
        is_valid, issues = self.validator.validate_proposal(proposal)
        
        if not is_valid:
            logger.warning(f"Proposal validation failed: {issues}")
            proposal.metadata['validation_issues'] = issues
            return False
        
        # Add final metadata
        proposal.metadata['created_at'] = datetime.now().isoformat()
        proposal.metadata['validated'] = True
        
        # Estimate impact
        proposal.estimated_impact = {
            'time_saved_seconds': self._estimate_time_saved(proposal),
            'prevented_failures': self._estimate_prevented_failures(proposal),
            'risk_level': self._calculate_risk_level(proposal)
        }
        
        return True
    
    def _generate_signature(self, stage: str, error_type: str, error_detail: str) -> str:
        """Generate unique signature for a rule."""
        # Create deterministic signature
        detail_hash = hashlib.md5(error_detail.encode()).hexdigest()[:8]
        return f"{stage}:{error_type}:{detail_hash}"
    
    def _generate_cache_key(self, stage: str, error: str) -> str:
        """Generate cache key for proposal."""
        # Normalize error for caching
        normalized = re.sub(r'[^a-zA-Z0-9]', '', error.lower())[:50]
        return f"{stage}:{normalized}"
    
    def _estimate_time_saved(self, proposal: RuleProposal) -> float:
        """Estimate time saved by automation (seconds)."""
        # Base estimates by command type
        if proposal.fix_command.startswith('pip install'):
            return 30.0  # Package installation
        elif proposal.fix_command.startswith('chmod'):
            return 10.0  # Permission fix
        elif proposal.fix_command.startswith('mkdir'):
            return 5.0   # Directory creation
        else:
            return 15.0  # Default
    
    def _estimate_prevented_failures(self, proposal: RuleProposal) -> int:
        """Estimate number of future failures prevented."""
        # Based on confidence and pattern type
        base = int(proposal.confidence * 10)
        
        # Common patterns prevent more failures
        if 'ModuleNotFoundError' in proposal.check_expression:
            base *= 2
        
        return base
    
    def _calculate_risk_level(self, proposal: RuleProposal) -> str:
        """Calculate risk level of applying this rule."""
        if proposal.safety_score >= 0.9:
            return "low"
        elif proposal.safety_score >= 0.7:
            return "medium"
        else:
            return "high"
    
    def test_proposal(self, proposal: RuleProposal) -> Dict[str, Any]:
        """
        Test a proposal against its test cases.
        
        Returns:
            Test results with pass/fail for each case
        """
        results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        for test_case in proposal.test_cases:
            try:
                # Create context for evaluation
                context = {
                    'stage': test_case['stage'],
                    'error': test_case['error']
                }
                
                # Evaluate expression
                result = eval(proposal.check_expression, {"__builtins__": {}}, context)
                expected = test_case['should_match']
                
                passed = result == expected
                
                results['details'].append({
                    'test': test_case,
                    'result': result,
                    'expected': expected,
                    'passed': passed
                })
                
                if passed:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'test': test_case,
                    'error': str(e),
                    'passed': False
                })
        
        return results
    
    def export_proposal(self, proposal: RuleProposal, filepath: Path) -> None:
        """Export proposal to file for review."""
        data = {
            'proposal': proposal.to_dict(),
            'validation': self.validator.validate_proposal(proposal),
            'test_results': self.test_proposal(proposal),
            'exported_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Proposal exported to {filepath}")
    
    def get_proposal_statistics(self) -> Dict[str, Any]:
        """Get statistics about generated proposals."""
        return {
            'total_proposals': len(self.proposal_cache),
            'average_confidence': sum(p.confidence for p in self.proposal_cache.values()) / len(self.proposal_cache) if self.proposal_cache else 0,
            'average_safety_score': sum(p.safety_score for p in self.proposal_cache.values()) / len(self.proposal_cache) if self.proposal_cache else 0,
            'proposals_by_stage': self._count_by_stage(),
            'common_patterns': self._get_common_patterns()
        }
    
    def _count_by_stage(self) -> Dict[str, int]:
        """Count proposals by stage."""
        counts = {}
        for proposal in self.proposal_cache.values():
            # Extract stage from check expression
            if match := re.search(r"stage == '(\w+)'", proposal.check_expression):
                stage = match.group(1)
                counts[stage] = counts.get(stage, 0) + 1
        return counts
    
    def _get_common_patterns(self) -> List[Tuple[str, int]]:
        """Get most common error patterns."""
        patterns = {}
        for proposal in self.proposal_cache.values():
            # Extract error type from signature
            parts = proposal.signature.split(':')
            if len(parts) >= 2:
                error_type = parts[1]
                patterns[error_type] = patterns.get(error_type, 0) + 1
        
        return sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]


# Example usage and testing
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create mock Claude client for testing
    class MockClaudeClient:
        async def chat(self, prompt: str, max_tokens: int = 800):
            # Simulate Claude response
            from types import SimpleNamespace
            
            if "ModuleNotFoundError" in prompt:
                content = """
                SIGNATURE: execute:ModuleNotFoundError:pandas
                CHECK: stage == 'execute' and 'ModuleNotFoundError' in error and 'pandas' in error
                FIX: pip install pandas
                CONFIDENCE: 0.95
                EXPLANATION: Install missing pandas module required for data processing
                TEST_CASE: ModuleNotFoundError: No module named 'pandas'
                SAFETY_NOTES: Safe - installs well-known data analysis library
                """
            else:
                content = """
                SIGNATURE: validate:PermissionError:script
                CHECK: stage == 'validate' and 'Permission denied' in error and 'test.sh' in error
                FIX: chmod +x test.sh
                CONFIDENCE: 0.85
                EXPLANATION: Make test script executable
                TEST_CASE: PermissionError: Permission denied: './test.sh'
                SAFETY_NOTES: Safe - only changes file permissions for specific file
                """
            
            return SimpleNamespace(content=content)
    
    # Create components
    client = MockClaudeClient()
    validator = RuleValidator()
    creator = RuleCreator(client, validator)
    
    # Test pattern matching
    print("Testing pattern matching...")
    proposal1 = creator._try_pattern_matching(
        "execute",
        "ModuleNotFoundError: No module named 'requests'"
    )
    if proposal1:
        print(f"Pattern match success: {proposal1.signature}")
        print(f"  Check: {proposal1.check_expression}")
        print(f"  Fix: {proposal1.fix_command}")
        print(f"  Safety: {proposal1.safety_score:.2f}")
    
    # Test async rule generation
    import asyncio
    
    async def test_generation():
        print("\nTesting Claude generation...")
        
        proposal2 = await creator.propose_rule(
            "execute",
            "ModuleNotFoundError: No module named 'pandas'",
            {'failure_count': 2, 'previous_fixes': ['pip install numpy']}
        )
        
        if proposal2:
            print(f"Generation success: {proposal2.signature}")
            print(f"  Confidence: {proposal2.confidence}")
            print(f"  Impact: {proposal2.estimated_impact}")
            
            # Test the proposal
            test_results = creator.test_proposal(proposal2)
            print(f"  Tests: {test_results['passed']}/{test_results['passed'] + test_results['failed']} passed")
            
            # Export for review
            creator.export_proposal(proposal2, Path("test_proposal.json"))
    
    asyncio.run(test_generation())
    
    # Show statistics
    print("\nProposal Statistics:")
    stats = creator.get_proposal_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Test validator directly
    print("\nTesting validator...")
    
    # Safe command
    safe_issues = validator.validate_command("pip install requests")
    print(f"Safe command issues: {safe_issues}")
    
    # Dangerous command
    dangerous_issues = validator.validate_command("rm -rf /")
    print(f"Dangerous command issues: {dangerous_issues}")
    
    # Clean up
    if Path("test_proposal.json").exists():
        Path("test_proposal.json").unlink()