# CAKE (Claude Autonomy Kit Engine) - Architecture Overview

## Executive Summary
CAKE is a deterministic intervention system that monitors LLM operations, prevents known failure patterns, and enforces safety guardrails without human escalation. It acts as an autonomous "operator" that watches, intervenes, and recovers from errors in real-time.

## Core Design Principles
1. **Zero-Escalation Autonomy**: Resolve all failures without paging humans
2. **Deterministic Interventions**: Template-driven, voice-consistent messages
3. **Pattern Memory**: Learn from repeated errors to prevent recurrence
4. **Safe-by-Default**: Block dangerous operations before execution
5. **Hot-Reloadable**: Configuration changes without service restart

## System Architecture

### Process Model
**All components run in-process in the same Python interpreter. No microservices.**

### Component Boundaries & Contracts

#### Required Components (MUST be present)
- **CakeController**: Central state machine orchestrator
- **Operator**: Intervention message generator
- **RecallDB**: Error pattern memory store
- **PTYShim**: Command interceptor
- **Validator**: Error classifier

#### Pluggable Components (MAY be replaced)
- **Adapters**: Integration layer (Claude Code, API, LUCA)
- **SnapshotManager**: State protection (can use external backup)
- **Metrics**: Observability layer (can use external telemetry)

### Contract Summary Table

| Component A | Component B | Method | Input Type | Output Type |
|------------|-------------|---------|------------|-------------|
| Watchdog | CakeController | `on_error_detected()` | `ErrorEvent` | None |
| CakeController | Validator | `classify_error()` | `ErrorEvent` | `Classification` |
| CakeController | RecallDB | `record_error()` | `str, dict` | None |
| CakeController | Operator | `build_message()` | `InterventionContext` | `str` |
| CakeController | Adapter | `inject_intervention()` | `str, dict` | None |
| Validator | RecallDB | `get_error_count()` | `str` | `int` |
| Operator | VoiceGate | `validate_voice_similarity()` | `str` | `float` |

### 1. Core Controller State Machine

**Interface**: `cake_controller.py`
```python
class CakeController:
    def transition_to(self, new_state: State, context: StateContext) -> None:
        """MUST validate transition and update all components"""
        
    def get_current_state(self) -> State:
        """MUST return current state enum"""
```

**States & Transitions:**
```yaml
states:
  MONITORING:
    entry: start_stream_monitors()
    exit: pause_monitors()
    transitions:
      - trigger: error_detected
        target: DETECTING
        condition: error_severity > threshold
        
  DETECTING:
    entry: classify_error(error_context)
    exit: log_classification()
    transitions:
      - trigger: false_positive
        target: MONITORING
      - trigger: intervention_required
        target: INTERVENING
        
  INTERVENING:
    entry: generate_intervention()
    exit: record_outcome()
    transitions:
      - trigger: fix_successful
        target: MONITORING
      - trigger: fix_failed
        target: RECOVERING
        
  RECOVERING:
    entry: attempt_rollback()
    exit: preserve_context()
    transitions:
      - trigger: alternative_found
        target: INTERVENING
      - trigger: no_alternatives
        target: ESCALATING
        
  ESCALATING:
    entry: safe_abort()
    exit: notify_human()
    transitions:
      - trigger: human_resolved
        target: MONITORING
```

### 2. Data Flow Examples

#### Error Detection → Intervention Flow
```yaml
1. Watchdog detects error:
   method: watchdog.monitor_stream()
   input: stderr stream bytes
   output: ErrorEvent object
   example:
     {
       "error_type": "ImportError",
       "file_path": "/workspace/main.py",
       "line_number": 10,
       "raw_output": "ImportError: No module named 'requests'",
       "timestamp": "2024-01-15T10:30:00Z",
       "stream_source": "stderr"
     }
   
2. Controller receives event:
   method: controller.on_error_detected(event)
   action: Calls validator.classify_error(event)
   
3. Validator classifies:
   method: validator.classify_error(event)
   input: ErrorEvent object
   output: Classification object
   example:
     {
       "error_type": "ImportError",
       "severity": "HIGH",
       "confidence": 0.95,
       "intervention_required": true,
       "suggested_fix": "pip install requests"
     }
   
4. RecallDB checks history:
   method: recall_db.get_error_count(signature)
   input: "sha256:abc123..."
   output: 3
   
5. Operator builds message:
   method: operator.build_message(context)
   input: InterventionContext object
   example_input:
     {
       "error_type": "ImportError",
       "file_path": "/workspace/main.py",
       "line_number": 10,
       "escalation_level": 1,
       "error_signature": "sha256:abc123...",
       "previous_interventions": [],
       "timestamp": "2024-01-15T10:30:00Z"
     }
   output: "Operator (CAKE): Stop. Run pip install requests. See requirements.txt."
   
6. Adapter injects:
   method: adapter.inject_intervention(message, context)
   input: (str, dict)
   output: None (message displayed in active session)
```

### 3. Error Handling Policy

**All fatal errors MUST be logged and raised to the Adapter for escalation.**

#### Component Failure Precedence
When multiple failure handlers would trigger:
1. Safety violations (PTYShim) take precedence - block immediately
2. System failures (component crash) - attempt restart
3. Logic errors (validation fails) - log and continue
4. Performance degradation - monitor and alert

#### Failure Response Matrix
| Component | Failure Type | Response | Escalation |
|-----------|-------------|----------|------------|
| Watchdog | Stream read error | Log WARNING, continue | None |
| Validator | Classification error | Default to MEDIUM severity | After 3 failures |
| RecallDB | Connection timeout | Retry 3x with backoff | Switch to in-memory |
| Operator | Voice check fail | Retry 3x simplified | Use safe default |
| Adapter | Injection failure | Switch to next adapter | Abort if all fail |

## Performance Requirements (MUST be met)
- **Latency**: ≤0.3s per 100 messages (measured by `test_100_message_benchmark.py`)
- **Coverage**: ≥90% test coverage (enforced by CI, blocks merge if not met)
- **Uptime**: 8-hour autonomous operation (validated by `test_autonomous_operation.py`)
- **Memory**: <1GB total footprint (monitored by `metrics.py`)
- **Command Validation**: <50ms response time (enforced by `test_pty_performance.py`)

## Configuration Management

**Configuration File**: `cake_config.yaml`
```yaml
# REQUIRED fields - MUST be present
version: "1.0"
strictness: balanced  # MUST be: minimal|balanced|paranoid
escalation:
  max_strikes: 4      # MUST be 1-10
  cooldown_minutes: 5 # MUST be 1-60
  
# OPTIONAL fields (defaults shown)
safety:
  blocked_commands: []  # Additional patterns to block
  allowed_domains: []   # Domain whitelist
performance:
  max_latency_ms: 300
  snapshot_retention_hours: 72
```

**Configuration Validation**:
```python
# MUST validate on load
if config['strictness'] not in ['minimal', 'balanced', 'paranoid']:
    raise ConfigurationError("Invalid strictness level")
if not 1 <= config['escalation']['max_strikes'] <= 10:
    raise ConfigurationError("max_strikes must be 1-10")
```

**Hot-Reload Behavior**:
- Changes detected within 1 second via file watch
- Validation MUST pass or config reverts to last valid state
- Components notified via `ConfigChangeEvent` broadcast
- No service restart required

## Metrics & Observability (REQUIRED)

**Prometheus Metrics** (exposed on port 9090):
```
cake_interventions_total{type, severity, success}
cake_response_latency_seconds{component, operation}
cake_rollback_operations{reason, success}
cake_errors_prevented_total{error_type}
cake_voice_similarity_score{message_type}
```

**Expected Good State Metrics**:
```
cake_interventions_total > 0 (after 1 hour)
cake_response_latency_seconds{p99} < 0.5
cake_errors_prevented_total > cake_interventions_total * 0.85
cake_voice_similarity_score > 0.9
```

## Integration Points

**Pre-execution Hook**:
```python
# MUST be called before any command execution
adapter.pre_execute_hook = lambda cmd: cake_controller.validate_command(cmd)
# Returns: CommandDecision(allowed=bool, reason=str)
```

**Post-execution Hook**:
```python
# MUST be called after command completion
adapter.post_execute_hook = lambda result: cake_controller.process_result(result)
# Input: ExecutionResult(exit_code=int, stdout=str, stderr=str)
```

**Intervention Injection**:
```python
# MUST be called when intervention needed
cake_controller.on_error = lambda error: adapter.inject_intervention(
    operator.build_message(InterventionContext.from_error(error))
)
# Returns: None (intervention displayed in session)
```

## Extending/Swapping Components

To replace a component:
1. Implement the required interface (see component specifications)
2. Register in `component_registry.py`
3. Update `cake_config.yaml` to use new component
4. Restart CAKE (hot-reload not supported for component swaps)

Example:
```python
# custom_recall_db.py
class CustomRecallDB(RecallDBInterface):
    def record_error(self, signature: str, context: dict) -> None:
        # Your implementation
        pass
    # ... implement all required methods

# component_registry.py
COMPONENTS = {
    'recall_db': {
        'default': 'recall_db.RecallDB',
        'custom': 'custom_recall_db.CustomRecallDB'
    }
}
```