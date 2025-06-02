#!/usr/bin/env python3
"""
Test suite for CAKE conversation parser
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from workflow.extraction.conversation_parser import (
    ConversationParser,
    ConversationTurn,
    ExtractedTask,
    ExtractedDecision,
    ProblemSolution,
    ConversationContext
)


class TestConversationParser:
    """Test the ConversationParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        with patch('spacy.load') as mock_load:
            # Mock spaCy model
            mock_nlp = Mock()
            mock_nlp.select_pipes = Mock()
            mock_load.return_value = mock_nlp
            
            parser = ConversationParser()
            parser.nlp = mock_nlp
            return parser
    
    @pytest.fixture
    def sample_conversation(self):
        """Sample conversation in markdown format."""
        return """## 👤 User

I need to implement a parser for Claude conversations. We should use spaCy for NLP processing.

## 🤖 Assistant

I'll help you implement a conversation parser using spaCy. Let me create the parser component.

I've created `cake/components/conversation_parser.py` with the following features:
- Deterministic NLP processing
- Markdown structure parsing
- Task and decision extraction

```bash
./scripts/cake-lint.sh
```

## 👤 User

Great! Can you also add error handling?

## 🤖 Assistant

I'll add comprehensive error handling to the parser. This ensures robustness.

Fixed the issue with imports. The parser now handles errors gracefully.

## 👤 User

Let's create tests for the parser

## 🤖 Assistant

I've implemented comprehensive tests in `tests/unit/test_conversation_parser.py`. The key insight is that we need to mock spaCy for deterministic testing.
"""
    
    def test_parse_markdown_turns(self, parser, sample_conversation):
        """Test parsing conversation into turns."""
        turns = parser._parse_markdown_turns(sample_conversation)
        
        assert len(turns) == 6
        assert turns[0].speaker == 'human'
        assert turns[1].speaker == 'assistant'
        assert turns[2].speaker == 'human'
        assert turns[3].speaker == 'assistant'
        assert turns[4].speaker == 'human'
        assert turns[5].speaker == 'assistant'
        
        # Check content extraction
        assert 'implement a parser' in turns[0].content
        assert 'conversation_parser.py' in turns[1].content
    
    def test_extract_tasks(self, parser):
        """Test task extraction from human messages."""
        # Mock spaCy document
        mock_doc = Mock()
        mock_sent = Mock()
        mock_sent.text = "We need to implement a parser for conversations"
        mock_doc.sents = [mock_sent]
        
        turn = ConversationTurn(
            speaker='human',
            content="We need to implement a parser for conversations",
            turn_number=0
        )
        
        context = ConversationContext()
        current_tasks = {}
        
        # Mock the task extraction method
        parser._extract_task_from_sentence = Mock(return_value="implement a parser for conversations")
        
        parser._extract_human_content(turn, mock_doc, context, current_tasks)
        
        assert len(context.tasks) == 1
        assert context.tasks[0].text == "implement a parser for conversations"
        assert context.tasks[0].speaker == 'human'
    
    def test_extract_decisions(self, parser):
        """Test decision extraction from assistant messages."""
        mock_doc = Mock()
        mock_sent = Mock()
        mock_sent.text = "I've decided to use spaCy for NLP processing"
        mock_doc.sents = [mock_sent]
        
        turn = ConversationTurn(
            speaker='assistant',
            content="I've decided to use spaCy for NLP processing because it's deterministic",
            turn_number=1
        )
        
        context = ConversationContext()
        current_tasks = {}
        current_problems = {}
        
        # Mock the decision extraction
        parser._extract_decision_from_sentence = Mock(return_value="use spaCy for NLP processing")
        parser._extract_rationale = Mock(return_value="because it's deterministic")
        
        parser._extract_assistant_content(turn, mock_doc, context, current_tasks, current_problems)
        
        assert len(context.decisions) == 1
        assert context.decisions[0].text == "use spaCy for NLP processing"
        assert context.decisions[0].rationale == "because it's deterministic"
    
    def test_extract_files_and_commands(self, parser):
        """Test extraction of file paths and commands."""
        content = """
I've created `cake/components/conversation_parser.py` and updated `requirements-dev.txt`.

Run the following:
```bash
./scripts/cake-lint.sh
./scripts/cake-test.sh
```
"""
        file_mentions = set()
        command_mentions = set()
        
        parser._extract_files_and_commands(content, file_mentions, command_mentions)
        
        assert 'cake/components/conversation_parser.py' in file_mentions
        assert 'requirements-dev.txt' in file_mentions
        assert './scripts/cake-lint.sh' in command_mentions
        assert './scripts/cake-test.sh' in command_mentions
    
    def test_extract_problems_and_solutions(self, parser):
        """Test problem and solution extraction."""
        # Mock problem detection
        mock_doc_problem = Mock()
        mock_sent_problem = Mock()
        mock_sent_problem.text = "encountering an import error with spacy"
        mock_doc_problem.sents = [mock_sent_problem]
        
        # Mock solution detection
        mock_doc_solution = Mock()
        mock_sent_solution = Mock()
        mock_sent_solution.text = "fixed the import error by installing the model"
        mock_doc_solution.sents = [mock_sent_solution]
        
        context = ConversationContext()
        current_tasks = {}
        current_problems = {}
        
        # Process problem
        turn_problem = ConversationTurn(
            speaker='assistant',
            content="encountering an import error with spacy",
            turn_number=2
        )
        parser._extract_assistant_content(turn_problem, mock_doc_problem, context, current_tasks, current_problems)
        
        assert len(context.errors_encountered) == 1
        assert len(current_problems) == 1
        
        # Process solution
        turn_solution = ConversationTurn(
            speaker='assistant',
            content="fixed the import error by installing the model",
            turn_number=3
        )
        
        # Mock the relationship check
        parser._is_related = Mock(return_value=True)
        
        parser._extract_assistant_content(turn_solution, mock_doc_solution, context, current_tasks, current_problems)
        
        assert len(context.problems_solved) == 1
        assert 'import error' in context.problems_solved[0].problem
        assert 'fixed' in context.problems_solved[0].solution
    
    def test_deterministic_output(self, parser):
        """Test that parser produces deterministic output."""
        conversation = """## 👤 User
Let's create a test.

## 🤖 Assistant
I'll create a test for you.
"""
        
        # Mock spaCy processing to ensure determinism
        mock_doc = Mock()
        mock_sent = Mock()
        mock_sent.text = "test content"
        mock_doc.sents = [mock_sent]
        parser.nlp.return_value = mock_doc
        
        # Parse twice
        context1 = parser.parse_conversation(conversation)
        context2 = parser.parse_conversation(conversation)
        
        # Check hash consistency
        assert context1.conversation_hash == context2.conversation_hash
        assert context1.message_count == context2.message_count
    
    def test_confidence_scoring(self, parser):
        """Test confidence score calculation."""
        context = ConversationContext()
        
        # Add tasks with different characteristics
        task1 = ExtractedTask(
            text="implement comprehensive parser",
            context="We need to implement comprehensive parser",
            speaker="human",
            implemented=True
        )
        
        task2 = ExtractedTask(
            text="fix bug",
            context="fix bug",
            speaker="human",
            implemented=False
        )
        
        context.tasks = [task1, task2]
        
        # Add decision
        decision = ExtractedDecision(
            text="use spacy",
            rationale="it's deterministic"
        )
        context.decisions = [decision]
        
        parser._calculate_confidence_scores(context)
        
        assert task1.confidence == 0.9  # Implemented
        assert task2.confidence == 0.5  # Short description
        assert decision.confidence == 0.9  # Has rationale
    
    def test_cake_pattern_recognition(self, parser):
        """Test recognition of CAKE-specific patterns."""
        assert 'cake-workflow' in parser.cake_patterns['cake_scripts']
        assert 'CakeController' in parser.cake_patterns['cake_components']
        assert '.py' in parser.cake_patterns['file_extensions']
        
        # Test file extension validation
        content = "Created main.py and config.yaml"
        file_mentions = set()
        command_mentions = set()
        
        parser._extract_files_and_commands(content, file_mentions, command_mentions)
        
        assert 'main.py' in file_mentions
        assert 'config.yaml' in file_mentions
    
    def test_json_output(self, parser):
        """Test JSON serialization of context."""
        context = ConversationContext()
        
        task = ExtractedTask(
            text="implement parser",
            context="we need to implement parser",
            speaker="human",
            confidence=0.8
        )
        context.tasks.append(task)
        
        decision = ExtractedDecision(
            text="use spacy",
            rationale="deterministic",
            confidence=0.9
        )
        context.decisions.append(decision)
        
        json_output = parser.to_json(context)
        parsed = json.loads(json_output)
        
        assert len(parsed['tasks']) == 1
        assert parsed['tasks'][0]['text'] == "implement parser"
        assert parsed['tasks'][0]['confidence'] == 0.8
        
        assert len(parsed['decisions']) == 1
        assert parsed['decisions'][0]['text'] == "use spacy"
        assert parsed['decisions'][0]['rationale'] == "deterministic"
    
    def test_alternative_markdown_formats(self, parser):
        """Test parsing different markdown conversation formats."""
        # Format 1: Human:/Assistant:
        format1 = """Human: I need help with parsing.
Assistant: I'll help you with parsing.
"""
        
        turns1 = parser._parse_markdown_turns(format1)
        assert len(turns1) == 2
        assert turns1[0].speaker == 'human'
        assert turns1[1].speaker == 'assistant'
        
        # Format 2: **Human** / **Assistant**
        format2 = """**Human** Can you create a parser?
        
**Assistant** Yes, I'll create a parser for you.
"""
        
        turns2 = parser._parse_markdown_turns(format2)
        assert len(turns2) == 2
        assert turns2[0].speaker == 'human'
        assert turns2[1].speaker == 'assistant'
    
    def test_performance_benchmark(self, parser):
        """Test that parser meets performance requirements."""
        import time
        
        # Create a large conversation (500+ messages)
        large_conversation = ""
        for i in range(250):
            large_conversation += f"""## 👤 User
Message {i*2}: I need help with task {i}.

## 🤖 Assistant  
Message {i*2+1}: I'll help you with task {i}. Created file{i}.py.

"""
        
        # Mock spaCy to avoid actual NLP processing in benchmark
        mock_doc = Mock()
        mock_sent = Mock()
        mock_sent.text = "test"
        mock_doc.sents = [mock_sent]
        parser.nlp.return_value = mock_doc
        
        start_time = time.time()
        context = parser.parse_conversation(large_conversation)
        end_time = time.time()
        
        # Should parse 500+ messages in under 5 seconds
        assert end_time - start_time < 5.0
        assert context.message_count >= 500
    
    def test_error_handling(self, parser):
        """Test parser error handling."""
        # Test with empty conversation
        empty_context = parser.parse_conversation("")
        assert empty_context.message_count == 0
        assert len(empty_context.tasks) == 0
        
        # Test with malformed conversation
        malformed = "This is not a proper conversation format"
        malformed_context = parser.parse_conversation(malformed)
        assert malformed_context.message_count == 0
        
        # Test with None
        with pytest.raises(AttributeError):
            parser.parse_conversation(None)
    
    def test_implementation_linking(self, parser):
        """Test linking tasks to implementations."""
        # Mock spaCy docs
        mock_doc1 = Mock()
        mock_sent1 = Mock()
        mock_sent1.text = "we need to create a parser"
        mock_doc1.sents = [mock_sent1]
        
        mock_doc2 = Mock()
        mock_sent2 = Mock()
        mock_sent2.text = "i've created the parser component"
        mock_doc2.sents = [mock_sent2]
        
        context = ConversationContext()
        current_tasks = {}
        current_problems = {}
        
        # Add a task
        turn1 = ConversationTurn(speaker='human', content="We need to create a parser", turn_number=0)
        parser._extract_task_from_sentence = Mock(return_value="create a parser")
        parser._extract_human_content(turn1, mock_doc1, context, current_tasks)
        
        # Add implementation
        turn2 = ConversationTurn(speaker='assistant', content="I've created the parser component", turn_number=1)
        parser._extract_implementation_reference = Mock(return_value="the parser component")
        parser._is_related = Mock(return_value=True)
        parser._extract_assistant_content(turn2, mock_doc2, context, current_tasks, current_problems)
        
        # Check that task is marked as implemented
        assert context.tasks[0].implemented == True
        assert "created the parser" in context.tasks[0].implementation_ref