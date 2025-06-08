import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from cake.core.cake_controller import CakeController, ControllerState

# Configure logging for tests (optional, but can be helpful)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for verbose test logging


@pytest.fixture
def mock_config_path(tmp_path: Path) -> Path:
    """Creates a temporary config directory and a cake_config.yaml with test-friendly values."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True) # Ensure it can be re-run if tmp_path persists
    config_file = config_dir / "cake_config.yaml"

    test_config = {
        "max_stage_iterations": 2, "timeout_minutes": 1, "auto_retry": False,
        "strict_mode": False, "min_coverage": 80, "enable_snapshots": True,
        "detection_timeout": 0.05, "classification_timeout": 0.05,
        "recall_db_timeout": 0.05, "knowledge_ledger_timeout": 0.05,
        "operator_timeout": 0.05, "ptyshim_timeout": 0.05,
        "system_stability_check_timeout": 0.05,
        "snapshot_restore_timeout": 0.1, "snapshot_list_timeout": 0.05,
        "idle_loop_delay": 0.001, "error_state_delay": 0.001,
        "health_check_interval_seconds": 0.05, "max_restart_attempts": 2,
        "component_health_timeout": 0.02, "rollback_timeout": 0.1,
    }
    with open(config_file, 'w') as f:
        yaml.dump(test_config, f)

    # Create dummy db paths if components' __init__ expects them
    (config_dir / "recall.db").touch()
    (config_dir / "knowledge.db").touch()

    return config_dir


@pytest.fixture
def mock_dependencies_objects():
    """
    Provides a dictionary of instantiated AsyncMock objects for CakeController's direct dependencies.
    These mocks will be used as return_values for class patches.
    """
    # For RecallDB methods called with to_thread, the mock should be synchronous (MagicMock)
    recall_db_mock = MagicMock(spec=RecallDB)
    recall_db_mock.is_repeat_error = MagicMock(return_value=False)
    recall_db_mock.get_similar_interventions = MagicMock(return_value=[])
    recall_db_mock.record_error = MagicMock(return_value="mock_error_id")
    recall_db_mock.record_command = MagicMock(return_value="mock_cmd_id") # Add record_command
    recall_db_mock.cleanup_expired = MagicMock(return_value=0)
    recall_db_mock.get_health = AsyncMock(return_value={"status": "healthy"})

    return {
        'stage_router': AsyncMock(spec_set=['process_stage', 'get_next_stage']),
        'recall_db': recall_db_mock,
        'task_convergence_validator': AsyncMock(spec_set=['validate_convergence', 'get_health']),
        'knowledge_ledger': AsyncMock(spec_set=['get_best_strategy', 'record_outcome', 'get_health']),
        'rate_limiter': MagicMock(),
        'watchdog': MagicMock(spec_set=['add_callback', 'async_monitor_stream', 'stop_monitoring', 'get_health']),
        # pty_shim is no longer a direct dependency instance
        'snapshot_manager': AsyncMock(spec_set=['get_latest_snapshot_id', 'restore_snapshot', 'get_relevant_snapshot_id', 'get_health']),
        'claude_client': MagicMock()
    }


@pytest.fixture
def cake_controller_instance(mock_config_path, mock_dependencies_objects, monkeypatch):
    """
    Fixture to create a CakeController instance.
    It patches the class constructors of dependencies to return our pre-defined mocks.
    """
    # Define paths for patching based on where they are imported in cake_controller.py
    patch_targets = {
        'cake.core.cake_controller.StageRouter': mock_dependencies_objects['stage_router'],
        'cake.core.cake_controller.OperatorBuilder': MagicMock(return_value=mock_dependencies_objects['operator']), # OperatorBuilder() returns the operator mock
        'cake.core.cake_controller.RecallDB': mock_dependencies_objects['recall_db'],
        'cake.core.cake_controller.TaskConvergenceValidator': mock_dependencies_objects['validator'],
        'cake.core.cake_controller.CrossTaskKnowledgeLedger': mock_dependencies_objects['knowledge_ledger'],
        'cake.core.cake_controller.RateLimiter': mock_dependencies_objects['rate_limiter'],
        'cake.core.cake_controller.Watchdog': mock_dependencies_objects['watchdog'],
        'cake.core.cake_controller.PTYShim': mock_dependencies_objects['pty_shim'],
        'cake.core.cake_controller.SnapshotManager': mock_dependencies_objects['snapshot_manager'],
    }

    # Apply all patches except for Watchdog, which will be a real instance
    # but we can still mock its methods if needed for specific tests using monkeypatch or patch.object

    # Create a real Watchdog instance that will be used by the controller
    # Its methods can be individually mocked in tests if needed.
    real_watchdog_instance = MagicMock(spec=Watchdog) # Use MagicMock to allow arbitrary attribute/method access for now
    real_watchdog_instance.add_callback = MagicMock()
    real_watchdog_instance.async_monitor_stream = AsyncMock()
    real_watchdog_instance.stop_monitoring = MagicMock()
    real_watchdog_instance.get_health = AsyncMock(return_value={"status": "healthy"})


    # Patch other components as before
    # Patch other components as before (PTYShim is removed)
    patch_targets_other = {
        'cake.core.cake_controller.StageRouter': mock_dependencies_objects['stage_router'],
        'cake.core.cake_controller.CrossTaskKnowledgeLedger': mock_dependencies_objects['knowledge_ledger'],
        'cake.core.cake_controller.RateLimiter': mock_dependencies_objects['rate_limiter'],
        'cake.core.cake_controller.SnapshotManager': mock_dependencies_objects['snapshot_manager'],
    }

    # Patch classes that are instantiated directly by CakeController
    monkeypatch.setattr('cake.core.cake_controller.Watchdog', MagicMock(return_value=real_watchdog_instance))

    mock_operator_builder_class = MagicMock()
    mock_operator_builder_instance_for_patch = MagicMock(spec=OperatorBuilder) # Use spec for stricter mocking
    mock_operator_builder_instance_for_patch.build_message = MagicMock(return_value="Mocked operator message")
    mock_operator_builder_class.return_value = mock_operator_builder_instance_for_patch
    monkeypatch.setattr('cake.core.cake_controller.OperatorBuilder', mock_operator_builder_class)

    mock_intervention_analyzer_class = MagicMock()
    mock_intervention_analyzer_instance_for_patch = MagicMock(spec=InterventionAnalyzer)
    mock_intervention_analyzer_instance_for_patch.analyze_situation = MagicMock(return_value=None) # Default
    mock_intervention_analyzer_class.return_value = mock_intervention_analyzer_instance_for_patch
    monkeypatch.setattr('cake.core.cake_controller.InterventionAnalyzer', mock_intervention_analyzer_class)

    mock_task_convergence_validator_class = MagicMock()
    mock_task_convergence_validator_instance = mock_dependencies_objects['task_convergence_validator']
    mock_task_convergence_validator_class.return_value = mock_task_convergence_validator_instance
    monkeypatch.setattr('cake.core.cake_controller.TaskConvergenceValidator', mock_task_convergence_validator_class)

    monkeypatch.setattr('cake.core.cake_controller.RecallDB', MagicMock(return_value=mock_dependencies_objects['recall_db']))


    with patch.multiple('cake.core.cake_controller', **{name.split('.')[-1]: MagicMock(return_value=mock_obj) for name, mock_obj in patch_targets_other.items()}):
        if 'ErrorEvent' not in globals():
            from cake.core.watchdog import ErrorEvent as GlobalErrorEvent # type: ignore
            global ErrorEvent
            ErrorEvent = GlobalErrorEvent # type: ignore
        if 'InterventionContext' not in globals():
            from cake.components.operator import InterventionContext as GlobalInterventionContext, InterventionType as GlobalInterventionType # type: ignore
            global InterventionContext, InterventionType
            InterventionContext = GlobalInterventionContext # type: ignore
            InterventionType = GlobalInterventionType # type: ignore
        if 'subprocess' not in globals(): # Ensure subprocess is available for CompletedProcess
            import subprocess as global_subprocess
            global subprocess
            subprocess = global_subprocess # type: ignore

        controller = CakeController(config_path=mock_config_path, claude_client=mock_dependencies_objects['claude_client'])

        # Assign mocks for easier access
        controller.mock_stage_router = mock_dependencies_objects['stage_router']
        controller.operator_builder = mock_operator_builder_instance_for_patch
        controller.intervention_analyzer = mock_intervention_analyzer_instance_for_patch
        controller.recall_db = mock_dependencies_objects['recall_db']
        controller.task_convergence_validator = mock_task_convergence_validator_instance
        controller.mock_knowledge_ledger = mock_dependencies_objects['knowledge_ledger']
        controller.mock_rate_limiter = mock_dependencies_objects['rate_limiter']
        controller.watchdog = real_watchdog_instance
        # controller.mock_pty_shim no longer exists
        controller.mock_snapshot_manager = mock_dependencies_objects['snapshot_manager']
        controller.mock_claude_client = mock_dependencies_objects['claude_client']

        for name, mock_obj in mock_dependencies_objects.items():
            if name not in ['watchdog', 'claude_client', 'recall_db'] and hasattr(mock_obj, 'get_health'):
                 mock_obj.get_health.return_value = {"status": "healthy"}

        mock_task_convergence_validator_class.assert_called_once_with(claude_client=mock_dependencies_objects['claude_client'])
        mock_operator_builder_class.assert_called_once()
        mock_intervention_analyzer_class.assert_called_once()
        assert controller.recall_db == mock_dependencies_objects['recall_db']

        return controller


class TestCakeControllerInitialization:
    def test_initial_state_is_idle(self, cake_controller_instance: CakeController):
        assert cake_controller_instance.current_state == ControllerState.IDLE
        assert cake_controller_instance.abort_requested is False
        assert cake_controller_instance.restart_attempts == 0

    def test_components_are_initialized_and_mocked(self, cake_controller_instance: CakeController):
        # Check that the attributes on the controller instance are our mocks
        assert cake_controller_instance.stage_router == cake_controller_instance.mock_stage_router
        assert cake_controller_instance.operator == cake_controller_instance.mock_operator
        assert cake_controller_instance.recall_db == cake_controller_instance.mock_recall_db
        assert cake_controller_instance.validator == cake_controller_instance.mock_validator
        assert cake_controller_instance.knowledge_ledger == cake_controller_instance.mock_knowledge_ledger
        assert cake_controller_instance.rate_limiter == cake_controller_instance.mock_rate_limiter
        assert cake_controller_instance.watchdog == cake_controller_instance.mock_watchdog
        assert cake_controller_instance.pty_shim == cake_controller_instance.mock_pty_shim
        assert cake_controller_instance.snapshot_manager == cake_controller_instance.mock_snapshot_manager

        # Check if recall_db (example) was called during init (it is, with config_path)
        # The patching replaces the class, so RecallDB(config_path) becomes mock_recall_db_class(config_path)
        # and then mock_recall_db_class(config_path) returns the instance mock_dependencies_objects['recall_db'].
        # So we check if the class mock was called.
        # This part is tricky with class patching vs instance patching.
        # The current setup patches the class constructor to return our instance mock.
        # So, the __init__ of the actual RecallDB is not called.
        # Instead, the mock object itself is assigned.

    def test_config_loading_uses_defaults_if_file_missing(self, tmp_path: Path, mock_dependencies_objects):
        # Create an empty config_dir without cake_config.yaml
        empty_config_dir = tmp_path / "empty_config"
        empty_config_dir.mkdir()

        patch_targets = {
            'cake.core.cake_controller.StageRouter': mock_dependencies_objects['stage_router'],
            'cake.core.cake_controller.OperatorBuilder': MagicMock(return_value=mock_dependencies_objects['operator']),
            'cake.core.cake_controller.RecallDB': mock_dependencies_objects['recall_db'],
            'cake.core.cake_controller.TaskConvergenceValidator': mock_dependencies_objects['validator'],
            'cake.core.cake_controller.CrossTaskKnowledgeLedger': mock_dependencies_objects['knowledge_ledger'],
            'cake.core.cake_controller.RateLimiter': mock_dependencies_objects['rate_limiter'],
            'cake.core.cake_controller.Watchdog': mock_dependencies_objects['watchdog'],
            'cake.core.cake_controller.PTYShim': mock_dependencies_objects['pty_shim'],
            'cake.core.cake_controller.SnapshotManager': mock_dependencies_objects['snapshot_manager'],
        }
        with patch.multiple('cake.core.cake_controller', **{name.split('.')[-1]: MagicMock(return_value=mock_obj) for name, mock_obj in patch_targets.items()}):
            controller = CakeController(config_path=empty_config_dir)
            assert controller.config is not None
            # Check a default value that's not in our minimal test_config
            assert controller.config.get("max_stage_iterations") == 3
            assert controller.config.get("detection_timeout") == 60 # A default from _default_config

    def test_config_loading_merges_file_with_defaults(self, mock_config_path: Path, mock_dependencies_objects):
        # mock_config_path provides a file with some overrides
        # Check that a default value is present alongside an overridden value
        patch_targets = {
            'cake.core.cake_controller.StageRouter': mock_dependencies_objects['stage_router'],
            # ... other patches ...
        }
        # Simplified patch for brevity, assuming other patches are similar
        with patch.multiple('cake.core.cake_controller', **{name.split('.')[-1]: MagicMock(return_value=mock_dependencies_objects.get(name.split('.')[-1], MagicMock())) for name in ['StageRouter', 'OperatorBuilder', 'RecallDB', 'TaskConvergenceValidator', 'CrossTaskKnowledgeLedger', 'RateLimiter', 'Watchdog', 'PTYShim', 'SnapshotManager']}):
            controller = CakeController(config_path=mock_config_path)
        assert controller.config.get("idle_loop_delay") == 0.001 # Overridden
        assert controller.config.get("max_stage_iterations") == 3 # Default, not in test_config

    def test_config_loading_handles_empty_yaml_file(self, tmp_path: Path, mock_dependencies_objects, caplog):
        caplog.set_level(logging.WARNING)
        config_dir = tmp_path / "empty_yaml_config"
        config_dir.mkdir()
        config_file = config_dir / "cake_config.yaml"
        config_file.write_text("") # Empty file

        patch_targets = { name.split('.')[-1]: MagicMock(return_value=mock_obj) for name, mock_obj in {
            'StageRouter': mock_dependencies_objects['stage_router'],
            'OperatorBuilder': MagicMock(return_value=mock_dependencies_objects['operator']),
            'RecallDB': mock_dependencies_objects['recall_db'],
            'TaskConvergenceValidator': mock_dependencies_objects['validator'],
            'CrossTaskKnowledgeLedger': mock_dependencies_objects['knowledge_ledger'],
            'RateLimiter': mock_dependencies_objects['rate_limiter'],
            'Watchdog': mock_dependencies_objects['watchdog'],
            'PTYShim': mock_dependencies_objects['pty_shim'],
            'SnapshotManager': mock_dependencies_objects['snapshot_manager'],
        }.items()}
        with patch.multiple('cake.core.cake_controller', **patch_targets):
            controller = CakeController(config_path=config_dir)

        assert "Configuration file" in caplog.text
        assert "is empty. Using defaults." in caplog.text
        assert controller.config.get("max_stage_iterations") == 3 # Default value

    def test_init_components_logs_critical_on_failure(self, mock_config_path, caplog):
        caplog.set_level(logging.CRITICAL)
        # Test that if a component fails to init, it's logged critically
        with patch('cake.core.cake_controller.Watchdog', side_effect=Exception("Watchdog init failed")):
            CakeController(config_path=mock_config_path) # We don't need the instance, just to trigger __init__
        assert "Failed to initialize a critical component: Watchdog init failed" in caplog.text


    def test_config_loading(self, cake_controller_instance: CakeController):
        assert cake_controller_instance.config is not None
        assert cake_controller_instance.config.get("idle_loop_delay") == 0.001
        assert cake_controller_instance.config.get("max_restart_attempts") == 2
        assert cake_controller_instance.config.get("health_check_interval_seconds") == 0.05


@pytest.mark.asyncio
class TestCakeControllerSetState:
    async def test_set_state_changes_current_state(self, cake_controller_instance: CakeController):
        assert cake_controller_instance.current_state == ControllerState.IDLE
        await cake_controller_instance.set_state(ControllerState.DETECTING)
        assert cake_controller_instance.current_state == ControllerState.DETECTING

    async def test_set_state_logs_transition(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        await cake_controller_instance.set_state(ControllerState.DETECTING)
        assert "Controller state changing from IDLE to DETECTING" in caplog.text

    async def test_set_state_calls_on_exit_and_on_enter(self, cake_controller_instance: CakeController):
        cake_controller_instance.on_exit_idle = AsyncMock()
        cake_controller_instance.on_enter_detecting = AsyncMock()

        await cake_controller_instance.set_state(ControllerState.DETECTING)

        cake_controller_instance.on_exit_idle.assert_awaited_once()
        cake_controller_instance.on_enter_detecting.assert_awaited_once()

    async def test_set_state_type_error(self, cake_controller_instance: CakeController):
        with pytest.raises(TypeError, match="new_state must be an instance of ControllerState"):
            await cake_controller_instance.set_state("NOT_A_STATE") # type: ignore

    async def test_set_state_no_change_if_already_in_state(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.DEBUG)
        cake_controller_instance.current_state = ControllerState.DETECTING

        # Make sure these would be called if logic was wrong
        cake_controller_instance.on_exit_detecting = AsyncMock()
        cake_controller_instance.on_enter_detecting = AsyncMock()

        await cake_controller_instance.set_state(ControllerState.DETECTING)

        cake_controller_instance.on_exit_detecting.assert_not_awaited()
        cake_controller_instance.on_enter_detecting.assert_not_awaited()
        assert "Controller already in state DETECTING" in caplog.text


@pytest.mark.asyncio
class TestCakeControllerDoIdle:
    async def test_do_idle_no_active_tasks_transitions_to_detecting(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.active_tasks = {}

        # Mock the specific transition method to check it was called
        with patch.object(cake_controller_instance, '_transition_to_detecting', new_callable=AsyncMock) as mock_transition:
            await cake_controller_instance._do_idle()

            assert "IDLE: No active tasks. Waiting for" in caplog.text
            assert "IDLE: Still no tasks after delay. Proactively transitioning to DETECTING for system check." in caplog.text
            mock_transition.assert_awaited_once()

    async def test_do_idle_with_active_tasks_transitions_to_detecting(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.active_tasks = {"task1": MagicMock()}

        with patch.object(cake_controller_instance, '_transition_to_detecting', new_callable=AsyncMock) as mock_transition:
            await cake_controller_instance._do_idle()

            assert "IDLE: Active tasks present. Transitioning to DETECTING." in caplog.text
            mock_transition.assert_awaited_once()

# This is just the beginning. Many more tests are needed.

# Import ErrorEvent globally for use in tests if not already defined via fixture
try:
    from cake.core.watchdog import ErrorEvent # type: ignore
except ImportError: # Handle if tests are run in a way that this path isn't immediately available
    # Define a dummy ErrorEvent for type hinting in tests if real one can't be imported
    @dataclass
    class ErrorEvent:
        error_type: str
        raw_output: str
        timestamp: datetime = field(default_factory=datetime.now)
        file_path: Optional[str] = None
        line_number: Optional[int] = None
        stream_source: str = "unknown"
        severity: str = "low" # Added for _is_critical_event testing

@pytest.mark.asyncio
class TestCakeControllerDetectingStateWithRealWatchdog:
    async def test_do_detecting_critical_event_from_queue_transitions_to_intervening(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        # Ensure ErrorEvent is defined, see above global import or dummy class
        mock_error_event = ErrorEvent(error_type="TestFailure", raw_output="test_function failed", stream_source="stderr", severity="high")
        await cake_controller_instance.event_queue.put(mock_error_event)

        # Mock _is_critical_event to ensure it's considered critical
        with patch.object(cake_controller_instance, '_is_critical_event', return_value=True) as mock_is_critical, \
             patch.object(cake_controller_instance, '_transition_to_intervening', new_callable=AsyncMock) as mock_transition:

            await cake_controller_instance._do_detecting()

            mock_is_critical.assert_called_once_with(mock_error_event)
            mock_transition.assert_awaited_once()

        assert cake_controller_instance.last_event == mock_error_event
        assert f"DETECTING: Critical event '{mock_error_event.error_type}' received. Transitioning to INTERVENING." in caplog.text
        assert cake_controller_instance.event_queue.empty() # Event should be consumed

    async def test_do_detecting_non_critical_event_from_queue_transitions_to_monitoring(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        mock_event = ErrorEvent(error_type="CoverageDrop", raw_output="Coverage at 80%", stream_source="stdout", severity="low")
        await cake_controller_instance.event_queue.put(mock_event)

        with patch.object(cake_controller_instance, '_is_critical_event', return_value=False) as mock_is_critical, \
             patch.object(cake_controller_instance, '_transition_to_monitoring', new_callable=AsyncMock) as mock_transition:

            await cake_controller_instance._do_detecting()

            mock_is_critical.assert_called_once_with(mock_event)
            mock_transition.assert_awaited_once()

        assert cake_controller_instance.last_event == mock_event
        assert f"DETECTING: Non-critical event '{mock_event.error_type}' received. Transitioning to MONITORING." in caplog.text

    async def test_do_detecting_queue_timeout_transitions_to_idle(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        # Ensure queue is empty
        assert cake_controller_instance.event_queue.empty()

        # Configure a very short queue timeout for the test
        original_timeout = cake_controller_instance.config.get("detection_queue_timeout")
        cake_controller_instance.config["detection_queue_timeout"] = 0.001

        with patch.object(cake_controller_instance, '_transition_to_idle', new_callable=AsyncMock) as mock_transition:
            await cake_controller_instance._do_detecting()
            mock_transition.assert_awaited_once()

        assert f"DETECTING: No event in queue after {0.001}s. Transitioning to IDLE." in caplog.text
        cake_controller_instance.config["detection_queue_timeout"] = original_timeout # Restore

    async def test_do_detecting_queue_processing_exception_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR)
        # Put a problematic "event" (e.g., not an ErrorEvent if _is_critical_event is not robust)
        # Or mock _is_critical_event to raise an error
        await cake_controller_instance.event_queue.put(ErrorEvent(error_type="Test", raw_output="Test", stream_source="test"))

        with patch.object(cake_controller_instance, '_is_critical_event', side_effect=Exception("Cannot decide criticality")) as mock_is_critical, \
             patch.object(cake_controller_instance, '_transition_to_error', new_callable=AsyncMock) as mock_transition:

            await cake_controller_instance._do_detecting()
            mock_transition.assert_awaited_once()

        assert "DETECTING: Error while processing event queue: Cannot decide criticality" in caplog.text

    async def test_handle_watchdog_event_puts_event_on_queue(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.DEBUG)
        mock_event = ErrorEvent(error_type="FileSystem", raw_output="Permissions issue", stream_source="kernel")

        await cake_controller_instance._handle_watchdog_event(mock_event)

        assert not cake_controller_instance.event_queue.empty()
        retrieved_event = await cake_controller_instance.event_queue.get()
        assert retrieved_event == mock_event
        assert f"Watchdog event received by controller callback: {mock_event}" in caplog.text
        assert f"Event {mock_event.error_type} enqueued for processing." in caplog.text

    async def test_watchdog_callback_is_registered(self, cake_controller_instance: CakeController):
        # The real_watchdog_instance is a MagicMock spec'd to Watchdog
        # So, add_callback is a MagicMock by default on it.
        cake_controller_instance.watchdog.add_callback.assert_called_once_with(
            cake_controller_instance._handle_watchdog_event
        )

@pytest.mark.asyncio
class TestStreamMonitoringConceptualMethods:
    async def test_start_task_stream_monitoring_creates_tasks(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        mock_stdout_reader = AsyncMock(spec=asyncio.StreamReader)
        mock_stderr_reader = AsyncMock(spec=asyncio.StreamReader)

        with patch('asyncio.create_task') as mock_create_task:
            await cake_controller_instance.start_task_stream_monitoring(mock_stdout_reader, mock_stderr_reader)

            assert mock_create_task.call_count == 2
            # Check that async_monitor_stream was called via create_task
            # The arguments to create_task are coroutines, so we check the method calls on watchdog
            cake_controller_instance.watchdog.async_monitor_stream.assert_any_call(mock_stdout_reader, "stdout")
            cake_controller_instance.watchdog.async_monitor_stream.assert_any_call(mock_stderr_reader, "stderr")

        assert "Starting task stream monitoring via Watchdog." in caplog.text

    async def test_stop_task_stream_monitoring_calls_watchdog_stop(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        await cake_controller_instance.stop_task_stream_monitoring()
        cake_controller_instance.watchdog.stop_monitoring.assert_called_once()
        assert "Requesting Watchdog to stop monitoring task streams." in caplog.text


# The following is a very basic test for the run loop to ensure it can execute one cycle.
@pytest.mark.asyncio
async def test_run_loop_single_pass_from_idle(cake_controller_instance: CakeController, caplog):
    """Test a single pass of the run loop starting from IDLE."""
    caplog.set_level(logging.DEBUG)

    # Configure mocks for a predictable flow from IDLE -> DETECTING -> IDLE
    cake_controller_instance.active_tasks = {} # Start with no tasks

    # Mock _do_idle to transition to detecting by calling set_state directly
    # This allows us to control the state change precisely for the test.
    async def custom_do_idle():
        logger.info("Custom _do_idle called, transitioning to DETECTING")
        await cake_controller_instance.set_state(ControllerState.DETECTING)
    cake_controller_instance._do_idle = AsyncMock(side_effect=custom_do_idle)

    # Mock watchdog to return no event, so _do_detecting should go back to IDLE
    cake_controller_instance.mock_watchdog.get_next_event = AsyncMock(return_value=None)

    # Patch set_state to break the loop after it's called enough times (IDLE->DETECTING, DETECTING->IDLE)
    # to prevent infinite loop in test and verify the transitions.
    original_set_state = cake_controller_instance.set_state
    set_state_call_log = []

    async def patched_set_state_for_run_loop_test(new_state: ControllerState):
        nonlocal set_state_call_log
        current_controller_state = cake_controller_instance.current_state # before change
        set_state_call_log.append((current_controller_state, new_state))

        # Call the original set_state
        await original_set_state(new_state)

        # Break condition: if we've transitioned back to IDLE from DETECTING
        if len(set_state_call_log) >= 2 and \
           set_state_call_log[0] == (ControllerState.IDLE, ControllerState.DETECTING) and \
           set_state_call_log[1] == (ControllerState.DETECTING, ControllerState.IDLE):
            # And the current state is now IDLE with no active tasks
            if cake_controller_instance.current_state == ControllerState.IDLE and not cake_controller_instance.active_tasks:
                raise asyncio.CancelledError("Test-induced loop break after IDLE->DETECTING->IDLE")

    with patch.object(cake_controller_instance, 'set_state', side_effect=patched_set_state_for_run_loop_test):
        with pytest.raises(asyncio.CancelledError, match="Test-induced loop break after IDLE->DETECTING->IDLE"):
            await cake_controller_instance.run()

    assert "RUN: Loop starting. Initial state: IDLE" in caplog.text
    assert "RUN: Executing main logic for state: IDLE" in caplog.text
    assert "Custom _do_idle called, transitioning to DETECTING" in caplog.text # From our custom _do_idle
    assert "Controller state changing from IDLE to DETECTING" in caplog.text
    assert "RUN: Executing main logic for state: DETECTING" in caplog.text
    assert "DETECTING: No significant events detected by Watchdog. Transitioning to IDLE." in caplog.text
    assert "Controller state changing from DETECTING to IDLE" in caplog.text
    assert "RUN: Main loop was cancelled." in caplog.text # Due to our test break

    cake_controller_instance.mock_watchdog.get_next_event.assert_awaited_once()
    assert len(set_state_call_log) >= 2
    assert set_state_call_log[0] == (ControllerState.IDLE, ControllerState.DETECTING)
    assert set_state_call_log[1] == (ControllerState.DETECTING, ControllerState.IDLE)


@pytest.mark.asyncio
class TestCakeControllerInterveningState:
    @pytest.fixture(autouse=True)
    def setup_intervening(self, cake_controller_instance: CakeController):
        # Ensure there's a last_event, as on_enter_intervening expects it
        cake_controller_instance.last_event = {"type": "anomaly", "details": "CPU spike", "severity": "high"}
        # Set the state to INTERVENING for these tests
        cake_controller_instance.current_state = ControllerState.INTERVENING

        # Default mock behaviors for components involved in INTERVENING
        # These can be overridden in specific tests for OperatorBuilder and InterventionAnalyzer
        # by configuring cake_controller_instance.operator_builder and cake_controller_instance.intervention_analyzer

        # Default for INTERVENING state tests - assume placeholder classification requires intervention
        # and analyzer returns some context, and operator builds some message.
        # This will be customized per test.

        # Example: Setup for a path where intervention IS generated
        # self.intervention_analyzer.analyze_situation will be mocked in tests
        # self.operator_builder.build_message will be mocked in tests

        cake_controller_instance.mock_recall_db.get_similar_interventions = AsyncMock(
            return_value=[{"strategy_id": "restart_service_X", "success_rate": 0.9}]
        ) # This is still used by the placeholder logic's downstream part
        cake_controller_instance.mock_knowledge_ledger.get_best_strategy = AsyncMock(
            return_value="restart_service_X"
        ) # Also used by placeholder's downstream
        cake_controller_instance.mock_pty_shim.execute_command = AsyncMock(
            return_value={"status": "success", "output": "service_X restarted"}
        )


    async def test_do_intervening_uses_analyzer_and_builder_success_path(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)

        # Setup mocks for this specific test
        mock_intervention_context = InterventionContext(InterventionType.REPEAT_ERROR, "testing") # type: ignore
        cake_controller_instance.intervention_analyzer.analyze_situation = MagicMock(return_value=mock_intervention_context)
        cake_controller_instance.operator_builder.build_message = MagicMock(return_value="Operator Message: Stop doing that.")

        # Ensure placeholder classification within _do_intervening deems intervention required
        # by setting up last_event appropriately.
        cake_controller_instance.last_event = ErrorEvent(error_type="TestFailure", raw_output="Fail", stream_source="stderr", severity="high")

        # Mock cake_exec which is now directly used by _do_intervening
        mock_completed_process = MagicMock(spec=subprocess.CompletedProcess)
        mock_completed_process.returncode = 0
        mock_completed_process.stdout = "Command executed successfully"
        mock_completed_process.stderr = ""

        with patch('cake.core.cake_controller.cake_exec', return_value=mock_completed_process) as mock_cake_exec, \
             patch.object(cake_controller_instance, '_transition_to_monitoring', new_callable=AsyncMock) as mock_transition_monitoring:

            await cake_controller_instance._do_intervening()

            mock_transition_monitoring.assert_awaited_once()
            cake_controller_instance.intervention_analyzer.analyze_situation.assert_called_once()
            cake_controller_instance.operator_builder.build_message.assert_called_once_with(mock_intervention_context)

            # Check if cake_exec was called (depends on placeholder logic for command determination)
            # This test assumes the placeholder logic for InterventionType.REPEAT_ERROR determines a command.
            if intervention_context_obj.intervention_type == InterventionType.REPEAT_ERROR: # type: ignore
                 mock_cake_exec.assert_called_once()

            assert "INTERVENING: Operator message built: Operator Message: Stop doing that." in caplog.text
            assert "INTERVENING: Intervention process completed successfully. Transitioning to MONITORING." in caplog.text

            cake_controller_instance.recall_db.record_error.assert_called_once()
            # Args for record_error: error_type, error_message, file_path, line_number, attempted_fix, context
            error_args, _ = cake_controller_instance.recall_db.record_error.call_args
            assert error_args[0] == cake_controller_instance.last_event.error_type # type: ignore
            assert error_args[1] == cake_controller_instance.last_event.raw_output # type: ignore
            # Attempted_fix_description depends on whether a command was run.
            # If mock_cake_exec was called, then attempted_fix should reflect that.
            if mock_cake_exec.called:
                assert "Successfully executed:" in error_args[4]
            else:
                assert "Intervention analyzed, message generated:" in error_args[4] # Or similar if no command path taken

            # Assert record_command was called if cake_exec was
            if mock_cake_exec.called:
                cake_controller_instance.recall_db.record_command.assert_called_once()
                cmd_args, _ = cake_controller_instance.recall_db.record_command.call_args
                assert cmd_args[1] is True # success
                assert "echo" in cmd_args[0] # Based on placeholder command


    async def test_do_intervening_analyzer_returns_no_intervention(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        # Setup event that placeholder logic will deem not requiring intervention
        # Example: A low severity, non-critical error type
        non_critical_event = ErrorEvent(error_type="MinorWarning", raw_output="Just a heads up", stream_source="stdout", severity="low")
        cake_controller_instance.last_event = non_critical_event

        with patch.object(cake_controller_instance, '_transition_to_monitoring', new_callable=AsyncMock) as mock_transition_monitoring:
            await cake_controller_instance._do_intervening()
            mock_transition_monitoring.assert_awaited_once()

        assert "INTERVENING: Placeholder classification - Intervention required: False." in caplog.text
        assert "INTERVENING: Placeholder classification indicates no intervention required. Transitioning to MONITORING." in caplog.text
        cake_controller_instance.mock_recall_db.get_similar_interventions.assert_not_awaited()

    async def test_do_intervening_pty_shim_command_fails_transitions_to_rollback(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.WARNING)
        cake_controller_instance.mock_pty_shim.execute_command = AsyncMock(
            return_value={"status": "failure", "output": "service_X failed to restart"}
        )

        with patch.object(cake_controller_instance, '_transition_to_rollback', new_callable=AsyncMock) as mock_transition_rollback:
            await cake_controller_instance._do_intervening()
            mock_transition_rollback.assert_awaited_once()

        assert "INTERVENING: PTYShim command 'sudo systemctl restart service_X' execution failed." in caplog.text
        assert "INTERVENING: Automated command failed. Transitioning to ROLLBACK." in caplog.text

    async def test_do_intervening_pty_shim_command_timeout_transitions_to_rollback(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR) # Timeout is logged as error in the method
        cake_controller_instance.mock_pty_shim.execute_command = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch.object(cake_controller_instance, '_transition_to_rollback', new_callable=AsyncMock) as mock_transition_rollback:
            await cake_controller_instance._do_intervening()
            mock_transition_rollback.assert_awaited_once()

        assert "INTERVENING: PTYShim command 'sudo systemctl restart service_X' execution timed out." in caplog.text
        assert "INTERVENING: Automated command failed. Transitioning to ROLLBACK." in caplog.text # This log comes after timeout handling

    async def test_do_intervening_manual_escalation_plan_transitions_to_monitoring(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.mock_operator.build_intervention_plan = AsyncMock(
            return_value={"type": "manual_escalation", "message": "Please check service Y."}
        )

        with patch.object(cake_controller_instance, '_transition_to_monitoring', new_callable=AsyncMock) as mock_transition_monitoring:
            await cake_controller_instance._do_intervening()
            mock_transition_monitoring.assert_awaited_once()

        assert "INTERVENING: Intervention plan requires manual escalation: Please check service Y." in caplog.text
        assert "INTERVENING: Intervention process completed successfully. Transitioning to MONITORING." in caplog.text # Assuming escalation is 'success' for now
        cake_controller_instance.mock_pty_shim.execute_command.assert_not_awaited()

    async def test_do_intervening_placeholder_classification_timeout_still_uses_placeholder(self, cake_controller_instance: CakeController, caplog):
        # This test might be less relevant as classification is now internal.
        # However, if placeholder logic involved an awaitable that could time out (it doesn't currently),
        # this would test that. For now, it shows the timeout for other components.
        caplog.set_level(logging.WARNING)
        # Let RecallDB timeout to test the general timeout handling in _do_intervening
        cake_controller_instance.mock_recall_db.get_similar_interventions = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch.object(cake_controller_instance, '_transition_to_rollback', new_callable=AsyncMock) as mock_transition_rollback:
            await cake_controller_instance._do_intervening()
            mock_transition_rollback.assert_awaited_once()

        assert "INTERVENING: A sub-process (classification, db, ledger, operator) timed out." in caplog.text # Generic timeout message
        assert "INTERVENING: Using placeholder logic to classify event" in caplog.text # Placeholder was still used

    async def test_do_intervening_knowledge_ledger_exception_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR)
        cake_controller_instance.mock_knowledge_ledger.get_best_strategy = AsyncMock(side_effect=Exception("Ledger meltdown"))

        with patch.object(cake_controller_instance, '_transition_to_error', new_callable=AsyncMock) as mock_transition_error:
            await cake_controller_instance._do_intervening()
            mock_transition_error.assert_awaited_once()

        assert "INTERVENING: Unexpected error during intervention logic: Ledger meltdown" in caplog.text

    async def test_on_enter_intervening_no_last_event_transitions_to_detecting(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.WARNING)
        cake_controller_instance.last_event = None # Force no last event

        # We need to call on_enter directly as _do_intervening wouldn't run its main logic
        # if on_enter already transitioned.
        with patch.object(cake_controller_instance, '_transition_to_detecting', new_callable=AsyncMock) as mock_transition_detecting:
            # Reset state to something else, so on_enter_intervening can be called by set_state
            cake_controller_instance.current_state = ControllerState.IDLE
            await cake_controller_instance.set_state(ControllerState.INTERVENING) # This will call on_enter_intervening

            mock_transition_detecting.assert_awaited_once()
        assert "INTERVENING: Entered without a last_event (anomaly context). This is unexpected. Transitioning to DETECTING." in caplog.text


@pytest.mark.asyncio
class TestCakeControllerMonitoringState:
    @pytest.fixture(autouse=True)
    def setup_monitoring(self, cake_controller_instance: CakeController):
        # Set the state to MONITORING for these tests
        cake_controller_instance.current_state = ControllerState.MONITORING
        # No default mock for validator.check_system_stability as it's now placeholder

    async def test_do_monitoring_system_stable_placeholder_transitions_to_idle(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.last_event = ErrorEvent(error_type="Resolved", raw_output="", stream_source="") # Simulate a previous event
        # Ensure event queue is empty for placeholder "stable" condition
        while not cake_controller_instance.event_queue.empty():
            cake_controller_instance.event_queue.get_nowait()
            cake_controller_instance.event_queue.task_done()

        with patch.object(cake_controller_instance, '_transition_to_idle', new_callable=AsyncMock) as mock_transition_idle:
            await cake_controller_instance._do_monitoring()
            mock_transition_idle.assert_awaited_once()

        assert cake_controller_instance.last_event is None # Should be cleared on stable
        assert "MONITORING: System deemed stable by placeholder logic." in caplog.text # Check new log
        # No direct call to validator.check_system_stability to assert

    async def test_do_monitoring_system_unstable_placeholder_with_last_event_transitions_to_rollback(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.last_event = ErrorEvent(error_type="PersistentProblem", raw_output="Still bad", stream_source="stderr")
        # Simulate event queue having a new event, making placeholder unstable
        await cake_controller_instance.event_queue.put(ErrorEvent(error_type="NewIssue", raw_output="Another one", stream_source="stderr"))


        with patch.object(cake_controller_instance, '_transition_to_rollback', new_callable=AsyncMock) as mock_transition_rollback:
            await cake_controller_instance._do_monitoring()
            mock_transition_rollback.assert_awaited_once()

        assert cake_controller_instance.last_event is not None
        assert "MONITORING: System deemed unstable by placeholder logic." in caplog.text
        assert "MONITORING: Instability (placeholder) and prior event context exists. Transitioning to ROLLBACK." in caplog.text
        # Clean up queue if needed for other tests, though fixture should handle it.
        if not cake_controller_instance.event_queue.empty():
            cake_controller_instance.event_queue.get_nowait()
            cake_controller_instance.event_queue.task_done()


    async def test_do_monitoring_system_unstable_placeholder_no_last_event_transitions_to_detecting(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.last_event = None
        await cake_controller_instance.event_queue.put(ErrorEvent(error_type="FreshProblem", raw_output="Something new", stream_source="stderr"))

        with patch.object(cake_controller_instance, '_transition_to_detecting', new_callable=AsyncMock) as mock_transition_detecting:
            await cake_controller_instance._do_monitoring()
            mock_transition_detecting.assert_awaited_once()

        assert "MONITORING: General system instability (placeholder). Transitioning to DETECTING." in caplog.text
        if not cake_controller_instance.event_queue.empty():
            cake_controller_instance.event_queue.get_nowait()
            cake_controller_instance.event_queue.task_done()

    # Timeout and general exceptions in _do_monitoring would now typically relate to event_queue operations
    # if the placeholder logic for stability check itself doesn't involve complex awaitables.
    # The current placeholder is very simple (checks queue.empty()), so direct timeout/exception test on it is less meaningful
    # unless we mock queue.get_nowait() to raise something, which is unusual.
    # The overall try-except in _do_monitoring would catch errors from transitions or other unexpected issues.
    async def test_do_monitoring_internal_exception_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR)
        # Make a transition itself fail to test the outer try-except in _do_monitoring
        with patch.object(cake_controller_instance, '_transition_to_idle', side_effect=Exception("Transition failed badly")):
             # Make placeholder logic decide to go to IDLE
            while not cake_controller_instance.event_queue.empty():
                cake_controller_instance.event_queue.get_nowait() # Clear queue for stable

            with patch.object(cake_controller_instance, '_transition_to_error', new_callable=AsyncMock) as mock_final_transition_to_error:
                await cake_controller_instance._do_monitoring()
                mock_final_transition_to_error.assert_awaited_once() # Should go to error state

        assert "MONITORING: Error during system stability check: Transition failed badly" in caplog.text # Log from the exception


@pytest.mark.asyncio
class TestCakeControllerRollbackState:
    @pytest.fixture(autouse=True)
    def setup_rollback(self, cake_controller_instance: CakeController):
        cake_controller_instance.current_state = ControllerState.ROLLBACK
        # Default mocks for snapshot manager
        cake_controller_instance.mock_snapshot_manager.get_latest_snapshot_id = AsyncMock(return_value="snap_123")
        cake_controller_instance.mock_snapshot_manager.restore_snapshot = AsyncMock(return_value=True)
        # Set some values that should be reset on successful rollback
        cake_controller_instance.abort_requested = True
        cake_controller_instance.restart_attempts = 1
        cake_controller_instance.last_event = {"details": "some event"}


    async def test_do_rollback_successful_transitions_to_idle_and_resets_flags(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)

        with patch.object(cake_controller_instance, '_transition_to_idle', new_callable=AsyncMock) as mock_transition_idle:
            await cake_controller_instance._do_rollback()
            mock_transition_idle.assert_awaited_once()

        assert "ROLLBACK: Successfully restored to snapshot 'snap_123'." in caplog.text
        assert "ROLLBACK: Transitioning to IDLE state after successful rollback." in caplog.text
        assert cake_controller_instance.abort_requested is False
        assert cake_controller_instance.restart_attempts == 0
        assert cake_controller_instance.last_event is None
        cake_controller_instance.mock_snapshot_manager.get_latest_snapshot_id.assert_awaited_once()
        cake_controller_instance.mock_snapshot_manager.restore_snapshot.assert_awaited_once_with("snap_123")

    async def test_do_rollback_no_snapshot_id_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.WARNING)
        cake_controller_instance.mock_snapshot_manager.get_latest_snapshot_id = AsyncMock(return_value=None)

        with patch.object(cake_controller_instance, '_transition_to_error', new_callable=AsyncMock) as mock_transition_error:
            await cake_controller_instance._do_rollback()
            mock_transition_error.assert_awaited_once()

        assert "ROLLBACK: No snapshot ID found by SnapshotManager. Cannot perform rollback. Transitioning to ERROR." in caplog.text
        assert cake_controller_instance.abort_requested is True # Not reset
        assert cake_controller_instance.restart_attempts == 1 # Not reset

    async def test_do_rollback_restore_snapshot_fails_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR)
        cake_controller_instance.mock_snapshot_manager.restore_snapshot = AsyncMock(return_value=False)

        with patch.object(cake_controller_instance, '_transition_to_error', new_callable=AsyncMock) as mock_transition_error:
            await cake_controller_instance._do_rollback()
            mock_transition_error.assert_awaited_once()

        assert "ROLLBACK: SnapshotManager reported failure to restore snapshot 'snap_123'. Transitioning to ERROR." in caplog.text
        assert cake_controller_instance.abort_requested is True # Not reset

    async def test_do_rollback_get_snapshot_id_timeout_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR)
        cake_controller_instance.mock_snapshot_manager.get_latest_snapshot_id = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch.object(cake_controller_instance, '_transition_to_error', new_callable=AsyncMock) as mock_transition_error:
            await cake_controller_instance._do_rollback()
            mock_transition_error.assert_awaited_once()

        assert "ROLLBACK: Operation timed out (either listing or restoring snapshot). Transitioning to ERROR." in caplog.text

    async def test_do_rollback_restore_snapshot_timeout_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR)
        cake_controller_instance.mock_snapshot_manager.restore_snapshot = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch.object(cake_controller_instance, '_transition_to_error', new_callable=AsyncMock) as mock_transition_error:
            await cake_controller_instance._do_rollback()
            mock_transition_error.assert_awaited_once()

        assert "ROLLBACK: Operation timed out (either listing or restoring snapshot). Transitioning to ERROR." in caplog.text

    async def test_do_rollback_snapshot_manager_missing_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR)
        del cake_controller_instance.snapshot_manager # Simulate component not being available

        with patch.object(cake_controller_instance, '_transition_to_error', new_callable=AsyncMock) as mock_transition_error:
            await cake_controller_instance._do_rollback()
            mock_transition_error.assert_awaited_once()

        assert "ROLLBACK: SnapshotManager component not found. Cannot perform rollback. Transitioning to ERROR." in caplog.text


@pytest.mark.asyncio
class TestCakeControllerErrorState:
    async def test_do_error_logs_context_and_sleeps(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR)
        cake_controller_instance.current_state = ControllerState.ERROR
        cake_controller_instance.last_event = {"type": "critical_failure"}
        cake_controller_instance.abort_requested = True

        # Mock asyncio.sleep to check it's called with the configured delay
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await cake_controller_instance._do_error()
            mock_sleep.assert_awaited_once_with(cake_controller_instance.config.get('error_state_delay'))

        assert "ERROR: Executing error state logic. System is considered halted and requires manual intervention." in caplog.text
        assert "ERROR: (_do_error) Last event context: {'type': 'critical_failure'}" in caplog.text
        assert "ERROR: (_do_error) Abort flag is active." in caplog.text
        # Note: _do_error itself doesn't transition. The run loop stops when state is ERROR.


@pytest.mark.asyncio
class TestCakeControllerHealthCheckAndRestart:
    async def test_check_health_all_components_healthy(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        # Default setup in cake_controller_instance fixture already mocks get_health to return healthy

        healthy = await cake_controller_instance.check_health()
        assert healthy is True
        assert "HEALTH: System health check PASSED." in caplog.text
        # Check a few component logs
        assert "HEALTH: Component 'watchdog' reported healthy." in caplog.text
        assert "HEALTH: Component 'validator' reported healthy." in caplog.text

    async def test_check_health_one_component_unhealthy(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.WARNING)
        cake_controller_instance.mock_watchdog.get_health = AsyncMock(return_value={"status": "unhealthy", "details": "Watchdog is napping"})

        healthy = await cake_controller_instance.check_health()
        assert healthy is False
        assert "HEALTH: Component 'watchdog' reported UNHEALTHY. Status: {'status': 'unhealthy', 'details': 'Watchdog is napping'}" in caplog.text
        assert "HEALTH: System health check FAILED." in caplog.text

    async def test_check_health_component_health_check_timeout(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.WARNING)
        cake_controller_instance.mock_validator.get_health = AsyncMock(side_effect=asyncio.TimeoutError)

        healthy = await cake_controller_instance.check_health()
        assert healthy is False
        assert "HEALTH: Component 'validator' timed out during health check." in caplog.text
        assert "HEALTH: System health check FAILED." in caplog.text

    async def test_check_health_component_missing(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.ERROR) # Logging critical component missing as ERROR
        original_watchdog = cake_controller_instance.watchdog
        cake_controller_instance.watchdog = None # type: ignore [assignment] # Test missing component

        healthy = await cake_controller_instance.check_health()
        assert healthy is False
        assert "HEALTH: Critical component 'watchdog' is missing (None)." in caplog.text
        assert "HEALTH: System health check FAILED." in caplog.text
        cake_controller_instance.watchdog = original_watchdog # Restore for other tests

    async def test_check_health_component_no_get_health_method(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.DEBUG)
        # RateLimiter is MagicMock and doesn't have get_health by default in our mock setup
        # Let's ensure one component *doesn't* have it for this test
        del cake_controller_instance.mock_rate_limiter.get_health # type: ignore

        healthy = await cake_controller_instance.check_health()
        # Will be true if other components are healthy
        assert healthy is True
        assert "HEALTH: Component 'rate_limiter' has no get_health() method. Assuming operational by presence." in caplog.text

    async def test_restart_controller_resets_state_and_components(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.current_state = ControllerState.DETECTING # Set to a non-IDLE state
        cake_controller_instance.last_event = {"type": "some_event"}
        cake_controller_instance.abort_requested = True

        # Mock _init_components to check it's called
        with patch.object(cake_controller_instance, '_init_components', wraps=cake_controller_instance._init_components) as mock_init_components:
            await cake_controller_instance._restart_controller()

        mock_init_components.assert_called_once()
        assert cake_controller_instance.current_state == ControllerState.IDLE
        assert cake_controller_instance.last_event is None
        assert cake_controller_instance.abort_requested is False # Restart should clear abort
        assert "RESTART: Attempting controller restart" in caplog.text
        assert "RESTART: Components re-initialized." in caplog.text
        assert "RESTART: Resetting controller state to IDLE." in caplog.text
        assert "RESTART: Controller restart attempt finished successfully." in caplog.text
        assert cake_controller_instance.restart_attempts == 1

    async def test_run_loop_health_check_triggers_restart_then_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.config["health_check_interval_seconds"] = 0.01 # Trigger health check quickly
        cake_controller_instance.config["max_restart_attempts"] = 1 # Allow only one restart for this test

        # Make check_health fail consistently
        cake_controller_instance.check_health = AsyncMock(return_value=False)
        # Mock _restart_controller to allow us to track calls and prevent full re-init if needed for simplicity here
        # but also to ensure it does its basic job of trying to set IDLE.
        restart_call_count = 0
        async def fake_restart():
            nonlocal restart_call_count
            restart_call_count += 1
            logging.info(f"FAKE_RESTART: Called (Attempt {restart_call_count})")
            # Simulate what _restart_controller does for state
            cake_controller_instance.restart_attempts = restart_call_count
            await cake_controller_instance.set_state(ControllerState.IDLE)
            # If we are on the last attempt that will fail, ensure check_health keeps returning false.
            if restart_call_count > cake_controller_instance.config["max_restart_attempts"]:
                 # This state won't be reached if max_restart_attempts logic is correct
                 logging.error("FAKE_RESTART: Should not have been called beyond max_restart_attempts")


        # The loop should:
        # 1. Start in IDLE (or enter it)
        # 2. _do_idle will transition to DETECTING (mock this to simplify)
        # 3. Health check runs, finds unhealthy.
        # 4. _restart_controller is called (our fake_restart). Sets state to IDLE. (restart_attempts = 1)
        # 5. Loop continues. _do_idle -> DETECTING.
        # 6. Health check runs, finds unhealthy again.
        # 7. Max restart attempts reached. Transitions to ERROR. Loop terminates.

        cake_controller_instance._do_idle = AsyncMock(side_effect=lambda: cake_controller_instance.set_state(ControllerState.DETECTING))
        cake_controller_instance._do_detecting = AsyncMock(side_effect=lambda: cake_controller_instance.set_state(ControllerState.IDLE)) # Simplified loop

        with patch.object(cake_controller_instance, '_restart_controller', side_effect=fake_restart) as mock_restart_method:
            # We expect the loop to eventually go to ERROR and terminate.
            # No specific exception, it should exit gracefully after setting ERROR.
            await cake_controller_instance.run()

        assert cake_controller_instance.check_health.call_count >= 2 # Called multiple times
        assert mock_restart_method.call_count == cake_controller_instance.config["max_restart_attempts"]
        assert "RUN: Health check returned UNHEALTHY." in caplog.text
        assert f"FAKE_RESTART: Called (Attempt {cake_controller_instance.config['max_restart_attempts']})" in caplog.text
        assert f"RUN: Maximum restart attempts ({cake_controller_instance.config['max_restart_attempts']}) reached after failed health check." in caplog.text
        assert cake_controller_instance.current_state == ControllerState.ERROR
        assert "RUN: Loop terminating due to ERROR state after health check/restart sequence." in caplog.text


    async def test_run_loop_health_check_resets_restart_attempts_on_healthy(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.config["health_check_interval_seconds"] = 0.01
        cake_controller_instance.restart_attempts = 1 # Start with some restart attempts

        # check_health will return True (default mock behavior)
        # _do_idle will transition to DETECTING, _do_detecting will transition back to IDLE
        # Then the loop will break because IDLE and no active tasks.
        cake_controller_instance._do_idle = AsyncMock(side_effect=lambda: cake_controller_instance.set_state(ControllerState.DETECTING))
        cake_controller_instance._do_detecting = AsyncMock(side_effect=lambda: cake_controller_instance.set_state(ControllerState.IDLE))

        # We need to ensure the loop runs enough for one health check and then exits.
        # Patch set_state to break after DETECTING -> IDLE transition
        original_set_state = cake_controller_instance.set_state
        async def patched_set_state_for_health_reset(new_state: ControllerState):
            await original_set_state(new_state)
            if new_state == ControllerState.IDLE and cake_controller_instance.current_state == ControllerState.IDLE: # current_state is now new_state
                # This means _do_detecting just transitioned to IDLE
                raise asyncio.CancelledError("Test break after one full cycle for health reset")

        with patch.object(cake_controller_instance, 'set_state', side_effect=patched_set_state_for_health_reset):
            with pytest.raises(asyncio.CancelledError, match="Test break after one full cycle for health reset"):
                await cake_controller_instance.run()

        assert "RUN: System is healthy. Resetting restart attempts counter from 1 to 0." in caplog.text
        assert cake_controller_instance.restart_attempts == 0


@pytest.mark.asyncio
class TestCakeControllerEmergencyAbort:
    async def test_emergency_abort_direct_call_sets_flag_and_state(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        assert cake_controller_instance.abort_requested is False
        cake_controller_instance.current_state = ControllerState.DETECTING # Start in a normal state

        await cake_controller_instance.emergency_abort(reason="Test direct abort")

        assert cake_controller_instance.abort_requested is True
        # emergency_abort calls set_state, so current_state should be ROLLBACK
        assert cake_controller_instance.current_state == ControllerState.ROLLBACK
        assert "EMERGENCY ABORT triggered! Reason: Test direct abort" in caplog.text
        assert "Emergency Abort: Forcing transition to ROLLBACK state." in caplog.text
        # Check that on_enter_rollback was called (implicitly by set_state)
        assert "Entering ROLLBACK state (Reason: Emergency Abort Triggered)." in caplog.text


    async def test_emergency_abort_when_already_in_rollback(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.current_state = ControllerState.ROLLBACK
        cake_controller_instance.abort_requested = False # Explicitly set for test clarity

        await cake_controller_instance.emergency_abort(reason="Abort while in rollback")

        assert cake_controller_instance.abort_requested is True
        assert cake_controller_instance.current_state == ControllerState.ROLLBACK # Stays in ROLLBACK
        assert "Emergency Abort: Already in ROLLBACK state. Abort flag is set, _do_rollback will handle." in caplog.text
        # set_state should not have been called to change state again
        assert "Controller state changing from ROLLBACK to ROLLBACK" not in caplog.text # Or check mock_set_state.call_count if patched

    async def test_run_loop_detects_abort_and_transitions_to_rollback(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.current_state = ControllerState.DETECTING # Start in a state that's not ROLLBACK/ERROR
        cake_controller_instance.abort_requested = True # Pre-set the abort flag

        # Mock _do_detecting to do nothing and prevent further state changes from it
        cake_controller_instance._do_detecting = AsyncMock()

        # We want the run loop to execute its abort check, then transition, then _do_rollback.
        # _do_rollback (mocked by default) will transition to IDLE, which will then break the loop.
        cake_controller_instance.mock_snapshot_manager.get_latest_snapshot_id = AsyncMock(return_value="snap_for_abort_test")
        cake_controller_instance.mock_snapshot_manager.restore_snapshot = AsyncMock(return_value=True)

        await cake_controller_instance.run() # Should execute one cycle, detect abort, run rollback, then exit

        assert "RUN: Abort requested. Current state: DETECTING." in caplog.text # From run loop
        assert "RUN: Abort detected, forcing transition to ROLLBACK state." in caplog.text
        assert "Controller state changing from DETECTING to ROLLBACK" in caplog.text
        assert "Entering ROLLBACK state (Reason: Emergency Abort Triggered)." in caplog.text # From on_enter_rollback
        assert "ROLLBACK: Executing rollback logic." in caplog.text # From _do_rollback
        assert "ROLLBACK: Successfully restored to snapshot 'snap_for_abort_test'." in caplog.text
        assert "Controller state changing from ROLLBACK to IDLE" in caplog.text # From successful rollback
        assert cake_controller_instance.current_state == ControllerState.IDLE
        assert cake_controller_instance.abort_requested is False # Reset by successful rollback

    async def test_run_loop_with_abort_already_in_rollback_proceeds_with_rollback(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.current_state = ControllerState.ROLLBACK # Start in ROLLBACK
        cake_controller_instance.abort_requested = True # Pre-set the abort flag

        cake_controller_instance.mock_snapshot_manager.get_latest_snapshot_id = AsyncMock(return_value="snap_for_abort_test_2")
        cake_controller_instance.mock_snapshot_manager.restore_snapshot = AsyncMock(return_value=True)

        # on_enter_rollback should be called by run() if it's the initial state
        # and then _do_rollback
        await cake_controller_instance.run()

        assert "RUN: Abort requested. Current state: ROLLBACK." in caplog.text # From run loop
        # It should not try to transition to ROLLBACK again if already there due to abort
        assert "RUN: Abort detected, forcing transition to ROLLBACK state." not in caplog.text
        assert "Entering ROLLBACK state (Reason: Emergency Abort Triggered)." in caplog.text
        assert "ROLLBACK: Executing rollback logic." in caplog.text
        assert cake_controller_instance.current_state == ControllerState.IDLE # After successful rollback
        assert cake_controller_instance.abort_requested is False


@pytest.mark.asyncio
class TestCakeControllerRunLoopComplexScenarios:

    async def test_run_loop_terminates_if_do_method_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)
        cake_controller_instance.current_state = ControllerState.DETECTING
        # Mock _do_detecting to directly transition to ERROR
        cake_controller_instance._do_detecting = AsyncMock(
            side_effect=lambda: cake_controller_instance.set_state(ControllerState.ERROR)
        )
        # Mock _do_error to prevent its actual sleep and allow quick test
        cake_controller_instance._do_error = AsyncMock()

        await cake_controller_instance.run()

        assert "RUN: Executing main logic for state: DETECTING" in caplog.text
        assert "Controller state changing from DETECTING to ERROR" in caplog.text
        assert "RUN: Loop terminating due to ERROR state after abort processing." in caplog.text # This log might need adjustment based on where error is set
        # Or "RUN: Loop terminated because controller entered ERROR state." if it breaks at while condition
        cake_controller_instance._do_error.assert_awaited_once() # Ensure final error processing is called

    async def test_run_loop_handles_cancelled_error_gracefully(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.INFO)

        # Mock a _do_ method to raise CancelledError after some initial work
        original_do_idle = cake_controller_instance._do_idle
        async def do_idle_then_cancel():
            await original_do_idle() # Do some initial work
            raise asyncio.CancelledError("Simulated cancellation during IDLE")
        cake_controller_instance._do_idle = AsyncMock(side_effect=do_idle_then_cancel)

        # We expect run to catch CancelledError and log it
        await cake_controller_instance.run()

        assert "RUN: Main loop was cancelled." in caplog.text
        assert "RUN: Main loop finished." in caplog.text # Finally block should still run

    async def test_run_loop_missing_do_method_transitions_to_error(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.CRITICAL) # This is a critical failure
        cake_controller_instance.current_state = ControllerState.DETECTING
        # Remove the _do_detecting method
        if hasattr(cake_controller_instance, '_do_detecting'):
            delattr(cake_controller_instance, '_do_detecting')

        cake_controller_instance._do_error = AsyncMock() # Mock to prevent sleep

        await cake_controller_instance.run()

        assert "RUN: No _do method found for state DETECTING! This is a code defect. Transitioning to ERROR." in caplog.text
        assert cake_controller_instance.current_state == ControllerState.ERROR
        cake_controller_instance._do_error.assert_awaited_once()

    async def test_health_check_during_restart_attempt_then_abort(self, cake_controller_instance: CakeController, caplog):
        """
        Scenario:
        1. Health check fails. Controller starts restart (attempt 1). State becomes IDLE.
        2. Before _do_idle runs in the new loop iteration, an emergency_abort is called.
        3. Controller should prioritize abort, go to ROLLBACK.
        4. Rollback succeeds, goes to IDLE. abort_requested is cleared.
        """
        caplog.set_level(logging.INFO)
        cake_controller_instance.config["health_check_interval_seconds"] = 0.01
        cake_controller_instance.config["max_restart_attempts"] = 2

        # Setup for health check failure
        cake_controller_instance.check_health = AsyncMock(return_value=False)

        # Mock _restart_controller to simulate partial restart then allow abort
        original_restart_controller = cake_controller_instance._restart_controller
        async def restart_then_allow_abort_and_run_once(*args, **kwargs):
            await original_restart_controller(*args, **kwargs) # This sets state to IDLE
            # Immediately after restart sets state to IDLE, trigger an abort
            logging.info("TEST_INTERVENTION: Triggering emergency_abort immediately after restart sets state to IDLE.")
            await cake_controller_instance.emergency_abort("Abort during restart recovery")
            # Make next health check pass to avoid further restarts
            cake_controller_instance.check_health = AsyncMock(return_value=True)

        # Mock _do_idle: if abort is requested, it shouldn't do much before run loop catches it.
        # If not aborted, it transitions to DETECTING.
        async def controlled_do_idle():
            if cake_controller_instance.abort_requested:
                logging.info("TEST_CONTROLLED_DO_IDLE: Abort requested, _do_idle doing minimal work.")
                await asyncio.sleep(0.001) # minimal delay
            else: # Should not happen in this test path if abort is quick
                logging.info("TEST_CONTROLLED_DO_IDLE: No abort, proceeding to DETECTING (unexpected path for this test).")
                await cake_controller_instance.set_state(ControllerState.DETECTING)

        cake_controller_instance._do_idle = AsyncMock(side_effect=controlled_do_idle)

        # Mock successful rollback
        cake_controller_instance.mock_snapshot_manager.get_latest_snapshot_id = AsyncMock(return_value="snap_abort_after_restart")
        cake_controller_instance.mock_snapshot_manager.restore_snapshot = AsyncMock(return_value=True)

        # Patch _restart_controller for the first restart attempt
        with patch.object(cake_controller_instance, '_restart_controller', side_effect=restart_then_allow_abort_and_run_once, autospec=True) as mock_restart:
            await cake_controller_instance.run()

        mock_restart.assert_called_once() # Should only restart once
        assert "RUN: Health check returned UNHEALTHY." in caplog.text
        assert "RESTART: Attempting controller restart (Attempt 1/2)" in caplog.text
        assert "TEST_INTERVENTION: Triggering emergency_abort immediately after restart sets state to IDLE." in caplog.text
        assert "EMERGENCY ABORT triggered! Reason: Abort during restart recovery" in caplog.text
        assert "Emergency Abort: Forcing transition to ROLLBACK state." in caplog.text # From emergency_abort call

        # Run loop detects abort, should already be in ROLLBACK or will transition.
        # Then _do_rollback runs.
        assert "Entering ROLLBACK state (Reason: Emergency Abort Triggered)." in caplog.text
        assert "ROLLBACK: Successfully restored to snapshot 'snap_abort_after_restart'." in caplog.text
        assert "Controller state changing from ROLLBACK to IDLE" in caplog.text

        assert cake_controller_instance.current_state == ControllerState.IDLE
        assert cake_controller_instance.abort_requested is False # Reset by successful rollback
        assert cake_controller_instance.restart_attempts == 0 # Reset by successful rollback


# TODO: Add selective logging tests with caplog for critical messages.

@pytest.mark.asyncio
class TestCakeControllerCriticalLogging:

    async def test_log_max_restart_attempts_reached(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.CRITICAL) # Capture critical messages
        cake_controller_instance.config["health_check_interval_seconds"] = 0.001
        cake_controller_instance.config["max_restart_attempts"] = 1
        cake_controller_instance.check_health = AsyncMock(return_value=False) # Consistently unhealthy

        # Mock _restart_controller to just increment attempt count and set IDLE
        async def simplified_restart():
            cake_controller_instance.restart_attempts +=1
            await cake_controller_instance.set_state(ControllerState.IDLE)
        cake_controller_instance._restart_controller = AsyncMock(side_effect=simplified_restart)

        # Mock _do_X methods to quickly cycle states if IDLE doesn't break the loop fast enough
        cake_controller_instance._do_idle = AsyncMock(side_effect=lambda: cake_controller_instance.set_state(ControllerState.DETECTING))
        cake_controller_instance._do_detecting = AsyncMock(side_effect=lambda: cake_controller_instance.set_state(ControllerState.IDLE)) # Cycle back
        cake_controller_instance._do_error = AsyncMock() # Prevent sleep

        await cake_controller_instance.run()

        assert "RUN: Maximum restart attempts (1) reached after failed health check. Transitioning to permanent ERROR state." in caplog.text
        assert cake_controller_instance.current_state == ControllerState.ERROR

    async def test_log_emergency_abort_triggered(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.CRITICAL)
        await cake_controller_instance.emergency_abort(reason="Logging test for abort")
        assert "EMERGENCY ABORT triggered! Reason: Logging test for abort" in caplog.text

    async def test_log_rollback_failure_no_snapshot(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.WARNING) # No snapshot is a WARNING during _do_rollback
        cake_controller_instance.current_state = ControllerState.ROLLBACK
        cake_controller_instance.mock_snapshot_manager.get_latest_snapshot_id = AsyncMock(return_value=None)
        cake_controller_instance._transition_to_error = AsyncMock() # Prevent actual state change for focused log check

        await cake_controller_instance._do_rollback()

        assert "ROLLBACK: No snapshot ID found by SnapshotManager. Cannot perform rollback. Transitioning to ERROR." in caplog.text

    async def test_log_missing_do_method(self, cake_controller_instance: CakeController, caplog):
        caplog.set_level(logging.CRITICAL)
        cake_controller_instance.current_state = ControllerState.DETECTING
        if hasattr(cake_controller_instance, '_do_detecting'):
            delattr(cake_controller_instance, '_do_detecting')
        cake_controller_instance._do_error = AsyncMock() # Prevent actual error state logic like sleep

        await cake_controller_instance.run()

        assert "RUN: No _do method found for state DETECTING! This is a code defect. Transitioning to ERROR." in caplog.text

# TODO: Run coverage and add tests for any missed branches.

def test_placeholder_to_ensure_file_is_valid_pytest_file():
    assert True
