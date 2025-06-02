#!/usr/bin/env python3
"""
CAKE Conversation Parser - Deterministic NLP-based conversation analyzer

This module provides high-quality, deterministic parsing of Claude conversations
to extract meaningful information for documentation generation.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import mistune
import spacy
from spacy.tokens import Doc, Span, Token

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation."""
    speaker: str  # 'human' or 'assistant'
    content: str
    timestamp: Optional[str] = None
    turn_number: int = 0
    markdown_ast: Optional[dict] = None


@dataclass
class ExtractedTask:
    """Represents a task discussed in the conversation."""
    text: str
    context: str
    speaker: str
    timestamp: Optional[str] = None
    implemented: bool = False
    implementation_ref: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ExtractedDecision:
    """Represents a decision made during the conversation."""
    text: str
    rationale: str
    alternatives_considered: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ProblemSolution:
    """Represents a problem and its solution."""
    problem: str
    solution: str
    result: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class ConversationContext:
    """Complete extracted context from a conversation."""
    tasks: List[ExtractedTask] = field(default_factory=list)
    decisions: List[ExtractedDecision] = field(default_factory=list)
    problems_solved: List[ProblemSolution] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    commands_run: List[str] = field(default_factory=list)
    key_insights: List[str] = field(default_factory=list)
    errors_encountered: List[str] = field(default_factory=list)
    message_count: int = 0
    conversation_hash: Optional[str] = None


class ConversationParser:
    """
    Deterministic NLP-based conversation parser for CAKE.
    
    Uses spaCy for semantic analysis and mistune for markdown parsing.
    All randomness is disabled to ensure deterministic output.
    """
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize the parser with spaCy model.
        
        Args:
            model_name: Name of the spaCy model to use
        """
        # Load spaCy with deterministic settings
        self.nlp = spacy.load(model_name)
        
        # Disable components that introduce randomness
        self.nlp.select_pipes(disable=["lemmatizer"])
        
        # Set random seed for any remaining randomness
        spacy.util.fix_random_seed(42)
        
        # Initialize markdown parser
        self.markdown = mistune.create_markdown(renderer='ast')
        
        # Pattern library for CAKE-specific terms
        self.cake_patterns = self._init_cake_patterns()
        
        # Task indicators - expanded for better coverage
        self.task_indicators = {
            # Requests
            'need to', 'we should', 'let\'s', 'can you', 'please create',
            'implement', 'create a', 'build a', 'add a', 'make a',
            'update the', 'fix the', 'we need', 'i need', 'shall we',
            'could you', 'would you', 'we were working on', 'help me',
            # Commands/directives
            'reorganize', 'refactor', 'improve', 'optimize', 'test',
            'analyze', 'review', 'check', 'verify', 'ensure',
            # Questions that imply tasks
            'how do we', 'what about', 'should we', 'can we',
            # Continuation
            'continue', 'finish', 'complete', 'follow up'
        }
        
        # Decision indicators - enhanced
        self.decision_indicators = {
            'decided to', 'will use', 'let\'s go with', 'we\'ll use',
            'i\'ll use', 'going with', 'choosing', 'opting for',
            'the plan is', 'the approach is', 'i recommend', 'my recommendation',
            'the solution is', 'we\'re going to', 'the best approach',
            'i suggest', 'let\'s use', 'we\'ll implement', 'the strategy is',
            'here\'s what we\'ll do', 'here\'s the plan', 'we\'ll follow'
        }
        
        # Implementation indicators - comprehensive
        self.implementation_indicators = {
            'i\'ve created', 'i\'ve implemented', 'i created', 'i implemented',
            'i\'ve added', 'i added', 'i\'ve updated', 'i updated',
            'i\'ve fixed', 'i fixed', 'here\'s the', 'this creates',
            'i\'ve written', 'i wrote', 'i\'ve built', 'i built',
            'i\'ve moved', 'i moved', 'i\'ve reorganized', 'let me create',
            'let me implement', 'let me add', 'let me update', 'let me fix',
            'creating', 'implementing', 'adding', 'now let\'s',
            'successfully', 'completed', 'done', 'finished'
        }
        
        # Problem indicators - more specific to avoid false positives
        self.problem_indicators = {
            'error:', 'error occurred', 'got an error', 'failed to', 'failure',
            'issue with', 'problem with', 'broken', 'not working', 'doesn\'t work',
            'bug in', 'failing', 'traceback', 'exception'
        }
        
        # Solution indicators
        self.solution_indicators = {
            'fixed', 'resolved', 'solved', 'working now', 'this fixes',
            'this resolves', 'this solves', 'the fix is', 'to fix this'
        }
    
    def _init_cake_patterns(self) -> Dict[str, List[str]]:
        """Initialize CAKE-specific pattern library."""
        return {
            'cake_scripts': [
                'cake-workflow', 'cake-status', 'cake-fix-ci', 'cake-handoff',
                'cake-extract-context', 'cake-create-pr', 'cake-lint',
                'cake-init', 'cake-stub-component', 'cake-test', 'cake-setup-dev',
                'cake-pre-commit', 'cake-check-voice', 'cake-generate-ci'
            ],
            'cake_components': [
                'CakeController', 'Operator', 'RecallDB', 'PTYShim',
                'Validator', 'Watchdog', 'SnapshotManager', 'VoiceSimilarityGate'
            ],
            'cake_concepts': [
                'zero-escalation', 'deterministic intervention', 'pattern memory',
                'safe-by-default', 'hot-reloadable', 'voice similarity',
                'error signature', 'escalation level'
            ],
            'file_extensions': [
                '.py', '.sh', '.md', '.yaml', '.yml', '.json', '.txt',
                '.log', '.toml', '.ini', '.cfg'
            ]
        }
    
    def parse_conversation(self, content: str) -> ConversationContext:
        """
        Parse a conversation and extract structured information.
        
        Args:
            content: Raw conversation text (markdown format)
            
        Returns:
            ConversationContext with extracted information
        """
        logger.info("Starting conversation parsing")
        
        # Calculate conversation hash for deterministic tracking
        conversation_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # Parse markdown structure
        turns = self._parse_markdown_turns(content)
        logger.info(f"Parsed {len(turns)} conversation turns")
        
        # Initialize context
        context = ConversationContext(
            message_count=len(turns),
            conversation_hash=conversation_hash
        )
        
        # Track conversation state
        current_tasks = {}  # task_id -> ExtractedTask
        current_problems = {}  # problem_id -> problem_text
        file_mentions = set()
        command_mentions = set()
        
        # Process each turn
        for i, turn in enumerate(turns):
            # Parse with spaCy
            doc = self.nlp(turn.content.lower())
            
            # Extract based on speaker
            if turn.speaker == 'human':
                self._extract_human_content(turn, doc, context, current_tasks)
            else:  # assistant
                self._extract_assistant_content(
                    turn, doc, context, current_tasks, current_problems
                )
            
            # Extract files and commands regardless of speaker
            self._extract_files_and_commands(turn.content, file_mentions, command_mentions)
            
            # Extract insights from original content (not lowercased)
            self._extract_insights(turn.content, doc, context)
        
        # Post-process extracted data
        context.files_modified = sorted(list(file_mentions))
        context.commands_run = sorted(list(command_mentions))
        
        # Deduplicate and clean up
        self._deduplicate_tasks(context)
        self._filter_errors(context)
        
        # Link problems to solutions
        self._link_problems_solutions(context)
        
        # Calculate confidence scores
        self._calculate_confidence_scores(context)
        
        logger.info(f"Extraction complete: {len(context.tasks)} tasks, "
                   f"{len(context.decisions)} decisions, "
                   f"{len(context.problems_solved)} problems solved")
        
        return context
    
    def _parse_markdown_turns(self, content: str) -> List[ConversationTurn]:
        """Parse markdown content into conversation turns."""
        turns = []
        
        # Try different markdown formats
        # Format 1: ## 👤 User / ## 🤖 Assistant
        # Format 2: Human: / Assistant:
        # Format 3: **Human** / **Assistant**
        
        lines = content.split('\n')
        current_speaker = None
        current_content = []
        turn_number = 0
        
        for i, line in enumerate(lines):
            # Check for speaker markers
            if any(marker in line for marker in ['## 👤 User', 'Human:', '**Human**']):
                # Save previous turn
                if current_speaker and current_content:
                    turns.append(ConversationTurn(
                        speaker=current_speaker,
                        content='\n'.join(current_content).strip(),
                        turn_number=turn_number
                    ))
                    turn_number += 1
                
                current_speaker = 'human'
                current_content = []
                
                # For "Human:" format, include content on same line
                if 'Human:' in line and not line.startswith('##'):
                    content_on_line = line.split('Human:', 1)[1].strip()
                    if content_on_line:
                        current_content.append(content_on_line)
                # For "**Human**" format
                elif '**Human**' in line:
                    content_on_line = line.split('**Human**', 1)[1].strip()
                    if content_on_line:
                        current_content.append(content_on_line)
                
            elif any(marker in line for marker in ['## 🤖 Assistant', '## 🤖 Claude', 
                                                   'Assistant:', '**Assistant**']):
                # Save previous turn
                if current_speaker and current_content:
                    turns.append(ConversationTurn(
                        speaker=current_speaker,
                        content='\n'.join(current_content).strip(),
                        turn_number=turn_number
                    ))
                    turn_number += 1
                
                current_speaker = 'assistant'
                current_content = []
                
                # For "Assistant:" format, include content on same line
                if 'Assistant:' in line and not line.startswith('##'):
                    content_on_line = line.split('Assistant:', 1)[1].strip()
                    if content_on_line:
                        current_content.append(content_on_line)
                # For "**Assistant**" format
                elif '**Assistant**' in line:
                    content_on_line = line.split('**Assistant**', 1)[1].strip()
                    if content_on_line:
                        current_content.append(content_on_line)
                
            elif current_speaker:
                # Skip markdown formatting lines
                if line.strip() and not line.strip() == '---':
                    current_content.append(line)
        
        # Don't forget the last turn
        if current_speaker and current_content:
            turns.append(ConversationTurn(
                speaker=current_speaker,
                content='\n'.join(current_content).strip(),
                turn_number=turn_number
            ))
        
        return turns
    
    def _extract_human_content(self, turn: ConversationTurn, doc: Doc, 
                              context: ConversationContext, 
                              current_tasks: Dict[str, ExtractedTask]) -> None:
        """Extract content from human turns."""
        # Use the original content for better extraction
        original_content = turn.content
        
        # Split into sentences
        sentences = [s.strip() for s in re.split(r'[.!?]+', original_content) if s.strip()]
        
        for sent_text in sentences:
            sent_lower = sent_text.lower()
            
            # Check for task indicators
            if any(indicator in sent_lower for indicator in self.task_indicators):
                # Extract the task description
                task_desc = self._extract_task_description(sent_text)
                if task_desc:
                    task = ExtractedTask(
                        text=task_desc,
                        context=sent_text,
                        speaker='human',
                        timestamp=turn.timestamp
                    )
                    
                    # Generate task ID for tracking
                    task_id = hashlib.md5(task_desc.encode()).hexdigest()[:8]
                    current_tasks[task_id] = task
                    context.tasks.append(task)
    
    def _extract_assistant_content(self, turn: ConversationTurn, doc: Doc,
                                  context: ConversationContext,
                                  current_tasks: Dict[str, ExtractedTask],
                                  current_problems: Dict[str, str]) -> None:
        """Extract content from assistant turns."""
        original_content = turn.content
        
        # Look for major accomplishments in headers
        accomplishment_patterns = [
            r'##\s*(.+?)\s*$',  # Markdown headers
            r'\*\*(.+?)\*\*',   # Bold text
            r'###\s*(.+?)\s*$'  # Smaller headers
        ]
        
        for pattern in accomplishment_patterns:
            matches = re.findall(pattern, original_content, re.MULTILINE)
            for match in matches:
                match_lower = match.lower()
                # Check if this is a decision or implementation
                if any(ind in match_lower for ind in ['implemented', 'created', 'built', 'fixed']):
                    # This is likely an implementation summary
                    # Find related tasks
                    for task in context.tasks:
                        if self._is_strongly_related(task.text, match):
                            task.implemented = True
                            task.implementation_ref = match
                            break
                elif any(ind in match_lower for ind in ['decided', 'chose', 'selected', 'using']):
                    # This is likely a decision
                    decision = ExtractedDecision(
                        text=match,
                        rationale=self._extract_rationale(original_content, match),
                        timestamp=turn.timestamp
                    )
                    context.decisions.append(decision)
        
        # Extract completed actions from lists
        list_pattern = r'^\s*[-*+•]\s+(.+)$'
        list_items = re.findall(list_pattern, original_content, re.MULTILINE)
        
        for item in list_items:
            item_lower = item.lower()
            # Check if this describes a completed action
            if any(ind in item_lower for ind in ['created', 'implemented', 'added', 
                                                 'updated', 'fixed', 'moved']):
                # Try to match with tasks
                for task in context.tasks:
                    if self._is_related(task.text, item):
                        task.implemented = True
                        if not task.implementation_ref:
                            task.implementation_ref = item
                        break
        
        # Look for decisions in specific patterns
        decision_patterns = [
            r'I\'ll (.+?)\.',
            r'Let me (.+?)\.',
            r'We\'ll (.+?)\.',
            r'The (.+?) approach (.+?)\.',
            r'Using (.+?) for (.+?)\.',
        ]
        
        for pattern in decision_patterns:
            matches = re.findall(pattern, original_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    decision_text = ' '.join(match)
                else:
                    decision_text = match
                    
                if len(decision_text.split()) > 3:
                    decision = ExtractedDecision(
                        text=decision_text,
                        rationale="",
                        timestamp=turn.timestamp
                    )
                    context.decisions.append(decision)
        
        # Look for errors and problems
        error_patterns = [
            r'error[:\s]+(.+?)(?:\.|$)',
            r'failed[:\s]+(.+?)(?:\.|$)',
            r'issue[:\s]+(.+?)(?:\.|$)'
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, original_content, re.IGNORECASE)
            for match in matches:
                if not any(skip in match.lower() for skip in ['no error', 'fixed', 'resolved']):
                    context.errors_encountered.append(match)
    
    def _extract_files_and_commands(self, content: str, 
                                   file_mentions: Set[str],
                                   command_mentions: Set[str]) -> None:
        """Extract file paths and commands from content."""
        # Extract file paths
        file_patterns = [
            r'(?:created?|modified?|updated?|edited?)\s+[`"]?([/\w.-]+\.\w+)[`"]?',
            r'(?:file|path):\s*[`"]?([/\w.-]+\.\w+)[`"]?',
            r'[`"]([/\w.-]+\.\w+)[`"]',
            r'\b([/\w.-]+\.\w+)\b'  # Generic file pattern
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, content, re.I)
            for match in matches:
                # Validate file extension
                if any(match.endswith(ext) for ext in self.cake_patterns['file_extensions']):
                    file_mentions.add(match)
        
        # Extract commands
        # First, extract from code blocks
        code_block_pattern = r'```bash\s*\n([^`]+)```'
        code_blocks = re.findall(code_block_pattern, content, re.MULTILINE | re.DOTALL)
        for block in code_blocks:
            # Extract individual commands from the block
            lines = block.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and any(script in line for script in self.cake_patterns['cake_scripts']):
                    command_mentions.add(line)
        
        # Also extract inline commands
        inline_patterns = [
            r'`(\./scripts/cake-[\w-]+\.sh[^\s`]*)`',
            r'(\./scripts/cake-[\w-]+\.sh[^\s`]*)'
        ]
        
        for pattern in inline_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if any(script in match for script in self.cake_patterns['cake_scripts']):
                    command_mentions.add(match.strip())
    
    def _extract_insights(self, content: str, doc: Doc, 
                         context: ConversationContext) -> None:
        """Extract key insights from content."""
        # Look for key insights in various formats
        insight_patterns = [
            r'(?:the key|important|note|remember):\s*(.+?)(?:\.|$)',
            r'(?:this ensures|this creates|this allows|this enables)\s+(.+?)(?:\.|$)',
            r'(?:benefit|advantage|improvement)(?:s)?:\s*(.+?)(?:\.|$)',
            r'\*\*(?:key|important|note):\*\*\s*(.+?)(?:\.|$)'
        ]
        
        for pattern in insight_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                insight = match.strip()
                if 20 < len(insight) < 300:  # Reasonable length
                    context.key_insights.append(insight)
        
        # Also look for insights in bullet points that start with key words
        bullet_pattern = r'^\s*[-*+•]\s+((?:key|important|note|benefit|advantage).+?)$'
        bullet_insights = re.findall(bullet_pattern, content, re.IGNORECASE | re.MULTILINE)
        for insight in bullet_insights:
            if 20 < len(insight) < 300:
                context.key_insights.append(insight)
    
    def _extract_task_description(self, sent_text: str) -> Optional[str]:
        """Extract a meaningful task description from text."""
        # Normalize the text
        sent_lower = sent_text.lower().strip()
        
        # High-level task patterns
        task_patterns = [
            (r'switch to (the )?(.+?)(?:\.|$)', 'Switch to {0}'),
            (r'change over to (the )?(.+?)(?:\.|$)', 'Change to {0}'),
            (r'implement (.+?)(?:\.|$)', 'Implement {0}'),
            (r'create (.+?)(?:\.|$)', 'Create {0}'),
            (r'test (.+?)(?:\.|$)', 'Test {0}'),
            (r'organize (.+?)(?:\.|$)', 'Organize {0}'),
            (r'work on (.+?)(?:\.|$)', 'Work on {0}'),
            (r'read (.+?)(?:\.|$)', 'Read {0}'),
            (r'explore (.+?)(?:\.|$)', 'Explore {0}'),
            (r'fix (.+?)(?:\.|$)', 'Fix {0}'),
            (r'update (.+?)(?:\.|$)', 'Update {0}'),
            (r'review (.+?)(?:\.|$)', 'Review {0}')
        ]
        
        # Check high-level patterns first
        for pattern, template in task_patterns:
            match = re.search(pattern, sent_lower)
            if match:
                # Get the captured group (skipping optional articles)
                captured = match.group(2) if match.lastindex > 1 else match.group(1)
                return template.format(captured)
        
        # Handle questions that imply tasks
        if '?' in sent_text:
            # Remove question mark and common question starters
            task = sent_text.strip('?')
            question_starts = ['can you', 'could you', 'would you', 'will you', 
                             'shall we', 'should we', 'do we need to']
            for start in question_starts:
                if task.lower().startswith(start):
                    task = task[len(start):].strip()
                    break
            
            # If it's a meaningful task after cleanup
            if len(task.split()) > 2:
                return task.capitalize()
        
        # Extract phrase after task indicator
        for indicator in ['let\'s', 'we need to', 'need to', 'we should', 
                         'i need', 'please', 'help me']:
            if indicator in sent_lower:
                idx = sent_lower.find(indicator)
                task = sent_text[idx + len(indicator):].strip()
                # Clean up
                task = task.strip('.!?,;')
                if len(task.split()) > 2:
                    return task.capitalize()
        
        # If sentence contains action verbs, use the whole sentence
        action_verbs = ['implement', 'create', 'build', 'test', 'fix', 
                       'organize', 'review', 'analyze', 'explore']
        if any(verb in sent_lower for verb in action_verbs):
            return sent_text.strip('.!?')
        
        return None
    
    def _extract_decision_from_sentence(self, sent: Span) -> Optional[str]:
        """Extract decision description from a sentence."""
        sent_text = sent.text.strip()
        sent_lower = sent_text.lower()
        
        # Look for clear decision patterns
        decision_patterns = [
            r'(?:decided to|will use|going with|choosing)\s+(.+?)(?:\.|$)',
            r'(?:the plan is|the approach is)\s+(.+?)(?:\.|$)',
            r'(?:we\'ll|i\'ll|let\'s)\s+(.+?)(?:\.|$)'
        ]
        
        for pattern in decision_patterns:
            match = re.search(pattern, sent_lower)
            if match:
                decision = match.group(1).strip()
                if len(decision.split()) > 3:
                    return decision.capitalize()
        
        # If sentence contains decision indicator, use more of the context
        for indicator in self.decision_indicators:
            if indicator in sent_lower:
                # Find the indicator position
                idx = sent_lower.find(indicator)
                # Get text after indicator
                decision = sent_text[idx:].strip('.!?')
                if len(decision.split()) > 4:
                    return decision
        
        return None
    
    def _extract_rationale(self, content: str, decision_text: str) -> str:
        """Extract rationale for a decision from surrounding context."""
        # Look for rationale indicators before or after the decision
        lines = content.split('\n')
        decision_line_idx = None
        
        for i, line in enumerate(lines):
            if decision_text in line:
                decision_line_idx = i
                break
        
        if decision_line_idx is None:
            return ""
        
        rationale_indicators = ['because', 'since', 'as', 'due to', 'for', 'to']
        rationale = ""
        
        # Check nearby lines
        for i in range(max(0, decision_line_idx - 2), 
                      min(len(lines), decision_line_idx + 3)):
            line = lines[i].lower()
            if any(indicator in line for indicator in rationale_indicators):
                rationale = lines[i]
                break
        
        return rationale
    
    def _extract_implementation_reference(self, text: str) -> Optional[str]:
        """Extract what was implemented from text."""
        # Remove implementation indicator
        impl_text = text
        for indicator in self.implementation_indicators:
            impl_text = impl_text.replace(indicator, '').strip()
        
        return impl_text if impl_text else None
    
    def _get_subtree_tokens(self, token: Token) -> List[Token]:
        """Get all tokens in a subtree."""
        tokens = [token]
        for child in token.children:
            tokens.extend(self._get_subtree_tokens(child))
        return tokens
    
    def _is_related(self, text1: str, text2: str) -> bool:
        """Check if two texts are related using token overlap."""
        # Simple token overlap for now
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        
        # Remove common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                       'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                       'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might'}
        tokens1 -= common_words
        tokens2 -= common_words
        
        # Calculate overlap
        overlap = len(tokens1 & tokens2)
        min_len = min(len(tokens1), len(tokens2))
        
        return overlap / min_len > 0.3 if min_len > 0 else False
    
    def _is_strongly_related(self, text1: str, text2: str) -> bool:
        """Check if two texts are strongly related (higher threshold)."""
        # Normalize
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        # Check for key term matches
        key_terms1 = re.findall(r'\b(\w{4,})\b', text1_lower)
        key_terms2 = re.findall(r'\b(\w{4,})\b', text2_lower)
        
        # Remove common words
        common_words = {'the', 'this', 'that', 'have', 'been', 'will', 'with', 'from'}
        key_terms1 = [t for t in key_terms1 if t not in common_words]
        key_terms2 = [t for t in key_terms2 if t not in common_words]
        
        # Calculate overlap
        if key_terms1 and key_terms2:
            overlap = len(set(key_terms1) & set(key_terms2))
            min_len = min(len(key_terms1), len(key_terms2))
            return overlap / min_len > 0.5 if min_len > 0 else False
        
        return False
    
    def _link_problems_solutions(self, context: ConversationContext) -> None:
        """Link problems to their solutions across the conversation."""
        # This is already partially done during extraction
        # Here we can do additional linking based on semantic similarity
        pass
    
    def _deduplicate_tasks(self, context: ConversationContext) -> None:
        """Remove duplicate tasks based on similarity."""
        unique_tasks = []
        seen_texts = set()
        
        for task in context.tasks:
            # Normalize for comparison
            normalized = ' '.join(task.text.lower().split())
            if normalized not in seen_texts:
                unique_tasks.append(task)
                seen_texts.add(normalized)
        
        context.tasks = unique_tasks
    
    def _filter_errors(self, context: ConversationContext) -> None:
        """Filter out non-error items from errors_encountered."""
        real_errors = []
        
        for error in context.errors_encountered:
            error_lower = error.lower()
            # Skip if it's explaining or describing errors
            skip_patterns = ['no error', 'fixed', 'resolved', 'the error message',
                           'error handling', 'if.*error', 'when.*error']
            if not any(pattern in error_lower for pattern in skip_patterns):
                # Check if it actually describes an error that occurred
                if any(ind in error_lower for ind in ['traceback', 'exception', 'failed']):
                    real_errors.append(error)
        
        context.errors_encountered = real_errors
    
    def _calculate_confidence_scores(self, context: ConversationContext) -> None:
        """Calculate confidence scores for extracted items."""
        # Simple heuristic-based confidence for now
        for task in context.tasks:
            # Higher confidence if implemented
            if task.implemented:
                task.confidence = 0.9
            else:
                # Based on clarity of task description
                task.confidence = 0.7 if len(task.text.split()) > 5 else 0.5
        
        for decision in context.decisions:
            # Higher confidence if rationale is present
            decision.confidence = 0.9 if decision.rationale else 0.7
    
    def to_json(self, context: ConversationContext) -> str:
        """Convert extracted context to JSON format."""
        return json.dumps({
            'tasks': [
                {
                    'text': t.text,
                    'context': t.context,
                    'speaker': t.speaker,
                    'timestamp': t.timestamp,
                    'implemented': t.implemented,
                    'implementation_ref': t.implementation_ref,
                    'confidence': t.confidence
                }
                for t in context.tasks
            ],
            'decisions': [
                {
                    'text': d.text,
                    'rationale': d.rationale,
                    'alternatives_considered': d.alternatives_considered,
                    'timestamp': d.timestamp,
                    'confidence': d.confidence
                }
                for d in context.decisions
            ],
            'problems_solved': [
                {
                    'problem': p.problem,
                    'solution': p.solution,
                    'result': p.result,
                    'timestamp': p.timestamp
                }
                for p in context.problems_solved
            ],
            'files_modified': context.files_modified,
            'commands_run': context.commands_run,
            'key_insights': context.key_insights,
            'errors_encountered': context.errors_encountered,
            'message_count': context.message_count,
            'conversation_hash': context.conversation_hash,
            'has_content': len(context.tasks) > 0 or len(context.decisions) > 0
        }, indent=2)


def main():
    """CLI interface for testing the parser."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse Claude conversation')
    parser.add_argument('input_file', help='Path to conversation file')
    parser.add_argument('-o', '--output', help='Output JSON file', 
                       default='conversation_context.json')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    
    # Read input file
    content = Path(args.input_file).read_text()
    
    # Parse conversation
    parser = ConversationParser()
    context = parser.parse_conversation(content)
    
    # Write output
    output_path = Path(args.output)
    output_path.write_text(parser.to_json(context))
    
    print(f"Parsed {context.message_count} messages")
    print(f"Extracted: {len(context.tasks)} tasks, {len(context.decisions)} decisions")
    print(f"Output written to: {output_path}")


if __name__ == '__main__':
    main()