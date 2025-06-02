#!/usr/bin/env python3
"""Tests for CAKE adapters module.

Tests core functionality of the adapters that integrate CAKE with Claude.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cake.adapters.cake_adapter import (
    CAKEAdapter,
    ConversationMessage,
    MessageRole,
    SystemState,
    create_cake_system,
)
from cake.adapters.cake_integration import CAKEIntegration
from cake.adapters.claude_orchestration import (
    ContextEnhancer,
    PromptContext,
    PromptExecution,
    PromptOrchestrator,
    PromptTemplate,
    PromptTemplateLibrary,
    PromptType,
    ResponseAnalyzer,
    ResponseQuality,
)


class TestCAKEAdapter:
    """Test the main CAKE adapter."""
    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""operator = Mock()
        operator.build_message.return_value = "Operator (CAKE): Stop. Fix the error. See docs."

        recall_db = Mock()
        recall_db.is_repeat_error.return_value = False
        recall_db.get_error_count.return_value = 0

        knowledge_ledger = Mock()
        knowledge_ledger.get_entry_count.return_value = 0

        validator = Mock()
        validator.validate_convergence.return_value = {"status": "success"}

        return {
            "operator": operator,
            "recall_db": recall_db,
            "knowledge_ledger": knowledge_ledger,
            "validator": validator,
        }

    def test_adapter_initialization(self, mock_components):
        """Test adapter initializes correctly."""adapter = CAKEAdapter(**mock_components)

        assert adapter.intervention_enabled is True
        assert adapter.auto_cleanup is True
        assert adapter.intervention_count == 0
        assert len(adapter.conversation_history) == 0

    def test_check_repeat_error_new_error(self, mock_components):
        """Test handling of new errors."""adapter = CAKEAdapter(**mock_components)
        error = {"message": "Module not found", "type": "ImportError"}

        result = adapter.check_repeat_error(error)

        assert result is None
        mock_components["recall_db"].record_error.assert_called_once()

    def test_check_repeat_error_repeated(self, mock_components):
        """Test handling of repeated errors."""mock_components["recall_db"].is_repeat_error.return_value = True
        adapter = CAKEAdapter(**mock_components)
        error = {"message": "Module not found", "type": "ImportError"}

        result = adapter.check_repeat_error(error)

        assert result is not None
        assert "Stop" in result
        mock_components["operator"].build_message.assert_called_once()

    def test_update_ci_status_failure(self, mock_components):
        """Test CI status update with failures."""adapter = CAKEAdapter(**mock_components)
        status = {
            "status": "failure",
            "failing_tests": ["test_foo", "test_bar"],
        }

        result = adapter.update_ci_status(status)

        assert result is not None
        assert adapter.current_state.ci_status == status

    def test_detect_feature_creep(self, mock_components):
        """Test feature creep detection."""adapter = CAKEAdapter(**mock_components)

        # No feature creep
        changes = {"new_files": ["test.py"], "new_functions": ["func1", "func2"]}
        assert adapter._detect_feature_creep(changes) is False

        # Feature creep detected
        changes = {
            "new_files": ["a.py", "b.py", "c.py"],
            "new_functions": [f"func{i}" for i in range(10)],
        }
        assert adapter._detect_feature_creep(changes) is True

    @pytest.mark.asyncio
    async def test_process_claude_action(self, mock_components):
        """Test processing Claude actions."""adapter = CAKEAdapter(**mock_components)
        action = {
            "type": "command",
            "command": "pip install requests",
            "stage": "execute",
        }

        result = await adapter.process_claude_action(action)

        assert adapter.current_state.current_action == "command"
        assert action["command"] in adapter.current_state.command_queue

    @pytest.mark.asyncio
    async def test_validate_task_convergence(self, mock_components):
        """Test task convergence validation."""adapter = CAKEAdapter(**mock_components)
        stage_outputs = {"think": "analyzed", "execute": "completed"}
        artifacts = ["main.py", "test_main.py"]

        result = await adapter.validate_task_convergence(stage_outputs, artifacts)

        assert result["status"] == "success"
        mock_components["validator"].validate_convergence.assert_called_once()


class TestCAKEIntegration:
    """Test the CAKE integration layer."""
    @pytest.fixture
    def integration(self):
        """Create integration instance for testing."""with patch("cake.adapters.cake_integration.create_cake_system") as mock_create:
            mock_adapter = Mock()
            mock_create.return_value = mock_adapter

            integration = CAKEIntegration(Path("/tmp/test_cake"))
            integration.adapter = mock_adapter

            return integration

    @pytest.mark.asyncio
    async def test_start_task(self, integration):
        """Test starting a new task."""task_desc = "Fix the import error"
        constitution = {"domain": "python", "min_coverage": 90}

        task_id = await integration.start_task(task_desc, constitution)

        assert task_id.startswith("task_")
        integration.adapter.update_task_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_stage(self, integration):
        """Test processing a TRRDEVS stage."""integration.adapter.process_claude_action = AsyncMock(return_value=None)

        result = await integration.process_stage("think", {"task": "analyze"})

        assert "interventions" in result
        assert result["stage"] == "think"

    def test_classify_task_type(self, integration):
        """Test task type classification."""assert integration._classify_task_type("Fix the bug in parser") == "bug_fix"
        assert integration._classify_task_type("Add new feature for export") == "feature"
        assert integration._classify_task_type("Refactor the database layer") == "refactor"
        assert integration._classify_task_type("Write tests for API") == "testing"
        assert integration._classify_task_type("Update documentation") == "general"


class TestPromptOrchestration:
    """Test the prompt orchestration system."""
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""mock_client = Mock()
        mock_client.chat = AsyncMock()
        mock_client.chat.return_value = Mock(content="Test response")

        orchestrator = PromptOrchestrator(
            claude_client=mock_client,
            persistence_path=Path("/tmp/test_prompts"),
        )

        return orchestrator

    def test_template_creation(self):
        """Test prompt template creation."""template = PromptTemplate(
            template_id="test_template",
            prompt_type=PromptType.ERROR_ANALYSIS,
            template_text="Analyze this error: $error_message",
            required_variables={"error_message"},
        )

        assert template.template_id == "test_template"
        assert "error_message" in template.required_variables

    def test_template_rendering(self):
        """Test template variable substitution."""template = PromptTemplate(
            template_id="test",
            prompt_type=PromptType.ERROR_ANALYSIS,
            template_text="Error: $error_message in $file",
            required_variables={"error_message", "file"},
        )

        rendered = template.render(
            {
                "error_message": "ImportError",
                "file": "main.py",
            }
        )

        assert "Error: ImportError in main.py" == rendered

    @pytest.mark.asyncio
    async def test_execute_prompt(self, orchestrator):
        """Test prompt execution."""context = PromptContext(
            stage="execute",
            task_description="Fix import error",
            error_context={"error": "ImportError: No module named 'requests'"},
        )

        execution = await orchestrator.execute_prompt(
            PromptType.ERROR_ANALYSIS,
            context,
        )

        assert isinstance(execution, PromptExecution)
        assert execution.response == "Test response"
        assert execution.token_usage["total_tokens"] > 0

    def test_response_analyzer(self):
        """Test response quality analysis."""analyzer = ResponseAnalyzer()

        response = """
        The error occurs because the 'requests' module is not installed.
        
        **Solution**:
        Run the following command:
        ```bash
        pip install requests
        ```
        
        This will install the required module and resolve the ImportError.
        """

        analysis = analyzer.analyze_response(
            response,
            PromptType.ERROR_ANALYSIS,
            expected_format=None,
        )

        assert analysis["overall_quality"] in [ResponseQuality.GOOD, ResponseQuality.EXCELLENT]
        assert analysis["quality_scores"]["completeness"] > 0.5
        assert "code_blocks" in analysis["extracted_data"]

    def test_context_enhancer(self):
        """Test context enhancement."""enhancer = ContextEnhancer()
        context = PromptContext(
            stage="execute",
            task_description="Fix the bug",
            error_context={"error": "TypeError"},
        )

        enhanced = enhancer.enhance_context(
            context,
            {"stage_history": ["think", "research"]},
        )

        assert "error_message" in enhanced
        assert enhanced["stage"] == "execute"
        assert enhanced["task_description"] == "Fix the bug"


class TestCreateCakeSystem:
    """Test the CAKE system factory."""
    def test_create_cake_system(self):
        """Test creating a complete CAKE system."""
        with patch("cake.adapters.cake_adapter.OperatorBuilder"), patch(
            "cake.adapters.cake_adapter.RecallDB"
        ), patch("cake.adapters.cake_adapter.CrossTaskKnowledgeLedger"), patch(
            "cake.adapters.cake_adapter.TaskConvergenceValidator"
        ):

            adapter = create_cake_system(config_path=Path("/tmp/test"))

            assert isinstance(adapter, CAKEAdapter)
            assert adapter.intervention_enabled is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
