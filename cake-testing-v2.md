# CAKE Testing Strategy & Validation Framework

**This is the authoritative testing contract for CAKE. All tests MUST pass for merge.**

## Test Execution Requirements

### Running Tests (REQUIRED commands)
```bash
# Unit tests only (fast, <30s)
poetry run pytest tests/unit/ -v

# Integration tests (slower, ~5min)
poetry run pytest tests/integration/ -v

# Performance benchmarks (MUST pass for merge)
poetry run pytest tests/perf/ -v --benchmark-only

# Full test suite with coverage (REQUIRED for release)
poetry run pytest --cov=cake --cov-report=html --cov-fail-under=90

# Specific test file
poetry run pytest tests/unit/test_operator_voice.py -v
```

### CI Pipeline Requirements
```yaml
# .github/workflows/ci.yml (REQUIRED)
name: CAKE CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run linters
        run: |
          poetry run black --check .
          poetry run isort --check .
          poetry run flake8 .
          poetry run mypy .
          
      - name: Run tests with coverage
        run: |
          poetry run pytest --cov=cake --cov-fail-under=90
          
      - name: Run performance tests
        run: |
          poetry run pytest tests/perf/ --benchmark-json=benchmark.json
          python scripts/check_benchmarks.py benchmark.json
          
      - name: Security scan
        run: |
          poetry run bandit -r cake/
          poetry run safety check
```

### Test Pass/Fail Policy
- **MUST PASS**: All unit tests (blocks merge)
- **MUST PASS**: All integration tests (blocks merge)
- **MUST PASS**: Coverage ≥90% (blocks merge)
- **MUST PASS**: Performance benchmarks (blocks merge)
- **MUST PASS**: All linters with zero errors (blocks merge)
- **MUST PASS**: Extended 8-hour test (blocks release)

### Test Addition Policy
**Every PR introducing a new component or logic branch MUST include new/updated tests.**
- PR author: Responsible for initial tests
- Reviewer: MUST verify test coverage before approval
- CI: MUST block merge if coverage drops

## Unit Test Specifications

### test_operator_voice.py
```python
class TestOperatorVoice:
    def test_voice_similarity_enforcement(self):
        """MUST verify all templates achieve ≥90% similarity"""
        # Input: Reference message
        # Expected: Similarity score ≥0.90
        
    def test_sentence_count_limit(self):
        """MUST reject messages with >3 sentences"""
        # Input: "Operator (CAKE): Stop. This is sentence one. This is two. This is three. This is four."
        # Expected: ValidationError raised
        
    def test_approved_verb_usage(self):
        """MUST use only: Run, Check, Fix, Try, See"""
        # Input: "Operator (CAKE): Stop. Execute pytest. Review output."
        # Expected: ValidationError (Execute not approved)
        
    def test_forbidden_patterns(self):
        """MUST NOT contain: sorry, apologies, I think, maybe"""
        # Input: "Operator (CAKE): Stop. I think you should run tests. Maybe check output."
        # Expected: ValidationError (forbidden patterns)
        
    def test_deterministic_output(self):
        """MUST produce identical output for same input"""
        # Input: Same InterventionContext 10 times
        # Expected: All 10 outputs identical
```

**Test Data Required**:
```json
{
  "reference_messages": [
    "Operator (CAKE): Stop. Run pytest. See test output.",
    "Operator (CAKE): Stop. Fix import. Check requirements.txt.",
    "Operator (CAKE): Stop. Try git stash. See changes."
  ],
  "invalid_messages": [
    "I think you should maybe try running tests",
    "Sorry, but there's an error. You might want to fix it.",
    "Operator (CAKE): This is a very long message that exceeds limits."
  ],
  "test_contexts": [
    {
      "error_type": "ImportError",
      "file_path": "/workspace/main.py",
      "line_number": 42,
      "error_message": "No module named 'requests'",
      "expected_output": "Operator (CAKE): Stop. Run pip install requests. See requirements.txt."
    }
  ]
}
```

### test_validator_accuracy.py
```python
class TestValidatorAccuracy:
    def test_error_detection_precision(self):
        """MUST detect >95% of real errors"""
        # Input: 100 real error outputs from error_corpus.json
        # Expected: ≥95 correctly classified
        
    def test_false_positive_rate(self):
        """MUST have <5% false positive rate"""
        # Input: 100 normal outputs (no errors)
        # Expected: ≤5 classified as errors
        
    def test_confidence_calibration(self):
        """MUST correlate confidence with actual accuracy"""
        # Input: Classifications with confidence 0.9
        # Expected: ~90% actually correct
        
    def test_all_error_types(self):
        """MUST handle: ImportError, SyntaxError, AttributeError, etc."""
        # Input: One example of each error type
        # Expected: All classified correctly
```

**Test Corpus Required** (`tests/data/error_corpus.json`):
```json
{
  "import_errors": [
    {
      "output": "ImportError: No module named 'requests'",
      "expected_type": "ImportError",
      "expected_severity": "HIGH",
      "expected_confidence": 0.95,
      "expected_fix": "pip install requests"
    }
  ],
  "syntax_errors": [
    {
      "output": "SyntaxError: invalid syntax (test.py, line 10)",
      "expected_type": "SyntaxError",
      "expected_severity": "HIGH",
      "expected_confidence": 0.98,
      "expected_fix": "Check syntax at line 10"
    }
  ],
  "test_failures": [
    {
      "output": "FAILED tests/test_main.py::test_function",
      "expected_type": "TestFailure",
      "expected_severity": "MEDIUM",
      "expected_confidence": 0.90,
      "expected_fix": null
    }
  ]
}
```

### test_recall_memory.py
```python
class TestRecallMemory:
    def test_concurrent_access_safety(self):
        """MUST handle 10 concurrent read/write operations"""
        # Setup: 10 threads writing different errors
        # Expected: No deadlocks, all writes succeed
        
    def test_ttl_enforcement(self):
        """MUST expire entries after 24 hours"""
        # Setup: Insert with timestamp 25 hours ago
        # Expected: Entry not returned in queries
        
    def test_query_performance(self):
        """MUST return results in <10ms for 10k records"""
        # Setup: Insert 10k error records
        # Expected: Query completes in <10ms
        
    def test_signature_uniqueness(self):
        """MUST generate unique signatures for different errors"""
        # Input: 100 slightly different errors
        # Expected: 100 unique signatures
```

**Performance Test Case**:
```python
@pytest.mark.benchmark
def test_recall_query_speed(benchmark, recall_db_with_10k_records):
    """Query must complete in <10ms"""
    result = benchmark(recall_db_with_10k_records.get_similar_errors, "test_signature")
    assert benchmark.stats['mean'] < 0.01  # <10ms
    assert len(result) >= 0  # Valid result
```

## Integration Test Specifications

### test_zero_escalation_flow.py (CRITICAL - MUST PASS)
```python
class TestZeroEscalation:
    """MUST prove 8-hour autonomous operation without human intervention"""
    
    def test_import_error_resolution(self):
        """
        Scenario: Missing module import
        Expected: Auto-add to requirements.txt
        Success: No human escalation triggered
        """
        # Test Case:
        # 1. Inject: "ImportError: No module named 'requests'"
        # 2. Expected intervention: "Operator (CAKE): Stop. Run pip install requests. See requirements.txt."
        # 3. Verify: Command executed, error resolved
        # 4. Assert: escalation_count == 0
        
    def test_test_failure_auto_fix(self):
        """
        Scenario: Syntax error causing test failure
        Expected: Specific fix guidance and application
        Success: Tests pass after intervention
        """
        # Test Case:
        # 1. Inject: "SyntaxError: invalid syntax (test.py, line 10)"
        # 2. Expected intervention: "Operator (CAKE): Stop. Fix syntax error line 10. Check parentheses."
        # 3. Verify: Guidance provided, developer fixes
        # 4. Assert: tests pass, escalation_count == 0
        
    def test_ci_bypass_prevention(self):
        """
        Scenario: Attempt force push with failing CI
        Expected: Block operation, rollback to green
        Success: Work preserved, CI protected
        """
        # Test Case:
        # 1. Setup: Tests failing, CI red
        # 2. Inject: "git push --force"
        # 3. Expected: Command blocked
        # 4. Expected intervention: "Operator (CAKE): Stop. Fix failing tests. Check CI status."
        # 5. Assert: push blocked, work preserved via stash
        
    def test_feature_creep_intervention(self):
        """
        Scenario: Developer solving wrong problem
        Expected: Detect drift, redirect to original
        Success: Original task completed
        """
        # Test Case:
        # 1. Setup: Task = "implement login"
        # 2. Detect: Changes to unrelated payment module
        # 3. Expected intervention: "Operator (CAKE): Stop. Check task scope. See original requirements."
        # 4. Assert: Developer redirected, original task completed
```

**Success Criteria**:
- Zero calls to escalation webhook
- All errors resolved autonomously  
- No human intervention required
- System remains operational throughout

**Test Evidence Required**:
```json
{
  "test_duration_hours": 8,
  "total_interventions": 42,
  "successful_resolutions": 42,
  "escalations_to_human": 0,
  "system_uptime_percent": 100,
  "errors_prevented": 38
}
```

### test_multi_component_flow.py
```python
class TestMultiComponent:
    def test_end_to_end_intervention_flow(self):
        """
        MUST verify complete flow:
        Watchdog → Validator → RecallDB → Operator → Adapter
        """
        # Test Case:
        # 1. Watchdog detects: "ImportError: No module named 'pandas'"
        # 2. Validator returns: Classification(severity="HIGH", intervention_required=True)
        # 3. RecallDB returns: occurrence_count=3
        # 4. Operator generates: "Operator (CAKE): Stop. Run pip install pandas. See requirements.txt."
        # 5. Adapter injects message
        # Assert: Each component called in order with correct data
        
    def test_configuration_hot_reload(self):
        """
        MUST verify config changes apply without restart
        """
        # Test Case:
        # 1. Start CAKE with strictness="balanced"
        # 2. Change to strictness="paranoid" in config file
        # 3. Wait 1 second
        # 4. Assert: New strictness active without restart
        # 5. Verify: No dropped messages during reload
        
    def test_adapter_switching(self):
        """
        MUST verify seamless adapter switching
        """
        # Test Case:
        # 1. Start with claude-code adapter
        # 2. Inject 5 interventions
        # 3. Switch to anthropic-api adapter
        # 4. Inject 5 more interventions
        # 5. Assert: All 10 interventions delivered
```

## Performance Test Specifications

### test_100_message_benchmark.py (EXPLICIT REQUIREMENT)
```python
class TestPerformanceBenchmarks:
    @pytest.mark.benchmark(group="latency")
    def test_100_message_latency(self, benchmark):
        """MUST process 100 messages in ≤0.3s"""
        messages = [
            {
                "error_type": "ImportError",
                "file_path": f"/workspace/file_{i}.py",
                "line_number": i,
                "error_message": f"No module named 'module_{i}'"
            }
            for i in range(100)
        ]
        
        def process_all():
            for msg in messages:
                context = create_intervention_context(msg)
                intervention = operator.build_message(context)
                validator.validate_message(intervention)
                
        result = benchmark(process_all)
        assert result.stats['mean'] <= 0.003  # 0.3s / 100
```

**Benchmark Thresholds** (scripts/check_benchmarks.py):
```python
PERFORMANCE_REQUIREMENTS = {
    "test_100_message_latency": 0.3,      # seconds
    "test_command_validation": 0.05,      # seconds  
    "test_snapshot_creation": 5.0,        # seconds
    "test_database_query": 0.01,          # seconds
    "test_intervention_generation": 0.1,  # seconds
}

# Script MUST fail if any benchmark exceeds threshold
for test_name, threshold in PERFORMANCE_REQUIREMENTS.items():
    if results[test_name] > threshold:
        print(f"FAIL: {test_name} took {results[test_name]}s (limit: {threshold}s)")
        sys.exit(1)
```

### test_memory_profile.py
```python
class TestMemoryUsage:
    def test_24_hour_memory_growth(self):
        """MUST not exceed 1GB after 24 hours"""
        # Test Case:
        # 1. Start CAKE with memory tracking
        # 2. Run normal operations for 24 hours (simulated)
        # 3. Assert: Total memory < 1GB
        # 4. Assert: No memory leaks detected
        
    def test_connection_pool_limits(self):
        """MUST not exceed 5 concurrent DB connections"""
        # Test Case:
        # 1. Spawn 10 concurrent operations
        # 2. Monitor DB connections
        # 3. Assert: Peak connections ≤ 5
        
    def test_snapshot_storage_limits(self):
        """MUST enforce 1GB snapshot storage limit"""
        # Test Case:
        # 1. Create snapshots until 1.1GB
        # 2. Assert: Oldest snapshots auto-deleted
        # 3. Assert: Total size ≤ 1GB
```

### test_stress_scenarios.py
```python
class TestStressScenarios:
    @pytest.mark.stress
    def test_high_error_rate(self):
        """MUST handle 1000 errors/minute"""
        # Test Case:
        # 1. Generate 1000 errors in 60 seconds
        # 2. Assert: All errors detected
        # 3. Assert: Appropriate interventions generated
        # 4. Assert: System remains responsive
        
    @pytest.mark.stress  
    def test_concurrent_operations(self):
        """MUST handle 50 concurrent operations"""
        # Test Case:
        # 1. Spawn 50 threads with different operations
        # 2. Assert: No deadlocks
        # 3. Assert: All operations complete
        # 4. Assert: Data consistency maintained
        
    @pytest.mark.stress
    def test_component_failure_recovery(self):
        """MUST recover from component crashes"""
        # Test Case:
        # 1. Kill RecallDB process
        # 2. Assert: System switches to in-memory mode
        # 3. Restart RecallDB
        # 4. Assert: System reconnects automatically
```

## Test Environment Setup

### Required Test Configuration
```yaml
# tests/test_config.yaml
test_mode: true
strictness: paranoid  # Use strictest mode for tests
database:
  path: ":memory:"    # In-memory for speed
logging:
  level: "DEBUG"
  file: "tests/test.log"
```

### Test Fixtures (tests/conftest.py)
```python
@pytest.fixture
def cake_controller():
    """MUST provide initialized controller"""
    controller = CakeController(config_path="tests/test_config.yaml")
    yield controller
    controller.cleanup()

@pytest.fixture
def mock_error_stream():
    """MUST provide error stream for testing"""
    return StringIO("ImportError: No module named 'requests'\n")

@pytest.fixture
def reference_corpus():
    """MUST provide voice reference data"""
    return load_json("tests/data/dustin_reference.json")

@pytest.fixture
def recall_db_with_10k_records():
    """MUST provide pre-populated database for performance tests"""
    db = RecallDB(":memory:")
    for i in range(10000):
        db.record_error(f"sig_{i}", {"error_type": "TestError"})
    return db
```

### Test Data and Reset Scripts

**Test Data Seeds** (`tests/data/`):
```
tests/data/
├── error_corpus.json         # 1000+ real error examples
├── dustin_reference.json     # 100+ reference voice samples
├── dangerous_commands.txt    # Commands to test blocking
├── test_scenarios.yaml       # Integration test scenarios
└── seed_database.sql         # Pre-populated test DB
```

**Reset Script** (`tests/reset_test_env.sh`):
```bash
#!/bin/bash
# MUST run before each test suite

# Clear any existing test data
rm -rf tests/test_output/
rm -f tests/*.log
rm -f tests/*.db

# Create fresh directories
mkdir -p tests/test_output/
mkdir -p tests/snapshots/

# Reset git test repo
cd tests/fixtures/git_repo/
git reset --hard HEAD
git clean -fd
cd -

echo "Test environment reset complete"
```

## Validation Requirements

### Coverage Requirements (ENFORCED)
```ini
# .coveragerc
[coverage:run]
source = cake
omit = 
    tests/*
    setup.py

[coverage:report]
fail_under = 90
precision = 2
show_missing = True

[coverage:html]
directory = htmlcov
```

### Coverage Breakdown Requirements
- Core components (controller, operator, validator): ≥95%
- Integration adapters: ≥90%
- Safety components (PTY shim, snapshots): ≥98%
- Utilities and helpers: ≥85%

### Required Test Data Files
```
tests/
├── data/
│   ├── error_corpus.json      # Real error examples
│   ├── dustin_reference.json  # Voice samples
│   ├── dangerous_commands.txt # Commands to block
│   └── test_scenarios.yaml    # Integration scenarios
├── fixtures/
│   ├── broken_code.py        # Intentionally broken
│   ├── requirements.txt      # For import testing
│   └── git_repo/            # Test git repository
```

## Success Metrics (MUST achieve all)

### Unit Tests
- **Pass Rate**: 100% (0 failures allowed)
- **Coverage**: ≥90% line and branch
- **Performance**: <30 seconds total runtime
- **Determinism**: Same input → same output

### Integration Tests  
- **Pass Rate**: 100% (0 failures allowed)
- **Scenarios**: All 4 zero-escalation scenarios pass
- **Runtime**: <5 minutes total
- **Stability**: No flaky tests allowed

### Performance Tests
- **Message Processing**: ≤0.3s per 100 messages
- **Command Validation**: <50ms per command
- **Database Queries**: <10ms per query
- **Memory Usage**: <1GB after 24 hours

### Autonomous Operation
- **Duration**: 8+ hours without intervention
- **Error Resolution**: >85% success rate
- **False Positives**: <5% rate
- **Human Escalations**: 0 (ZERO)

## Test Failure Protocol

### On Test Failure
1. **Block merge** (enforced by CI)
2. **Log failure details** with full context
3. **Create GitHub issue** with failure details
4. **Assign to PR author** for resolution

### On Performance Regression
1. **Compare to baseline** (last release)
2. **If >10% degradation**: Block merge
3. **Run profiler** to identify cause
4. **Document fix** in commit message

### On Coverage Drop
1. **If <90%**: Block merge automatically
2. **Generate report** showing uncovered lines
3. **Require tests** for uncovered code
4. **No exceptions** without CTO approval

### Remediation Timeline
- Unit test failures: Fix within 24 hours
- Integration test failures: Fix within 48 hours
- Performance regressions: Fix within 72 hours
- Coverage drops: Fix before next PR