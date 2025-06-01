# CAKE Component Specifications

**This is the authoritative implementation contract for all CAKE components.**

## 1. Operator System (Intervention Engine)

### operator.py - Template-Driven Message Builder

**Interface**:
```python
class Operator:
    def build_message(self, context: InterventionContext) -> str:
        """
        MUST return intervention message passing voice gate
        
        Args:
            context: InterventionContext with all required fields
            
        Returns:
            str: Intervention message (≤3 sentences)
            
        Raises:
            VoiceSimilarityError: If message fails ≥90% similarity check
            TemplateError: If template rendering fails
        """
        
    def get_escalation_level(self, error_signature: str) -> int:
        """
        MUST return current escalation level (1-4)
        
        Args:
            error_signature: SHA256 hash of normalized error
            
        Returns:
            int: Current strike count for this error
        """
```

**Input Format**:
```json
{
  "error_type": "ImportError",
  "file_path": "/workspace/main.py",
  "line_number": 42,
  "error_message": "No module named 'requests'",
  "escalation_level": 1,
  "suggested_fix": "pip install requests",
  "error_signature": "sha256:abc123def456...",
  "previous_interventions": [],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Output Requirements**:
- MUST match pattern: `"Operator (CAKE): Stop. {action}. {reference}."`
- MUST use only approved verbs: ["Run", "Check", "Fix", "Try", "See"]
- MUST be ≤3 sentences total
- MUST NOT include apologies or explanations

**Example Valid Outputs**:
```
"Operator (CAKE): Stop. Run pip install requests. See requirements.txt."
"Operator (CAKE): Stop. Fix syntax error line 42. Check parentheses."
"Operator (CAKE): Stop. Try git stash. See uncommitted changes."
```

**Failure Behavior**:
- On template error: Log ERROR, return safe default message
- On voice check fail: Retry with simplified message, max 3 attempts
- On all retries failed: Escalate with `InterventionType.SYSTEM_ERROR`

### voice_similarity_gate.py - Style Consistency Enforcer

**Interface**:
```python
class VoiceSimilarityGate:
    def validate_message(self, message: str) -> ValidationResult:
        """
        MUST validate message against reference corpus
        
        Args:
            message: Proposed intervention message
            
        Returns:
            ValidationResult(passed=bool, score=float, reason=str)
        """
        
    def load_reference_corpus(self, path: str) -> None:
        """
        MUST load and precompute embeddings for reference messages
        
        Args:
            path: Path to dustin_reference.json
            
        Raises:
            FileNotFoundError: If corpus file missing
            CorruptedCorpusError: If JSON invalid
        """
```

**Reference Corpus Format**:
```json
{
  "version": "1.0",
  "messages": [
    {
      "text": "Operator (CAKE): Stop. Run pytest. See test results.",
      "context": "test_failure",
      "success_rate": 0.92,
      "embedding": [0.123, 0.456, ...]
    }
  ]
}
```

**Validation Criteria**:
- Sentence count ≤3 (HARD REQUIREMENT)
- Similarity score ≥0.90 (HARD REQUIREMENT)
- Pattern match for "Operator (CAKE):" prefix
- No forbidden patterns (apologies, uncertainty)

**Example Validation**:
```python
result = gate.validate_message("Operator (CAKE): Stop. Run tests. See output.")
# Returns: ValidationResult(passed=True, score=0.94, reason="Valid")

result = gate.validate_message("I think you should maybe try running tests")
# Returns: ValidationResult(passed=False, score=0.45, reason="Missing operator prefix, uncertainty detected")
```

## 2. Monitoring & Detection Layer

### watchdog.py - Stream Monitor

**Interface**:
```python
class Watchdog:
    def monitor_stream(self, stream: IO, callback: Callable) -> None:
        """
        MUST monitor stream and trigger callback on patterns
        
        Args:
            stream: stdout or stderr stream object
            callback: Function to call with ErrorEvent
            
        Note: MUST be non-blocking
        """
        
    def add_pattern(self, pattern: str, error_type: str) -> None:
        """
        MUST add new error pattern to monitor
        
        Args:
            pattern: Regex pattern to match
            error_type: Classification for this pattern
        """
```

**Error Event Format**:
```python
@dataclass
class ErrorEvent:
    error_type: str  # "ImportError", "SyntaxError", etc.
    file_path: Optional[str]
    line_number: Optional[int]
    raw_output: str
    timestamp: datetime
    stream_source: str  # "stdout" or "stderr"
```

**Example ErrorEvent**:
```json
{
  "error_type": "ImportError",
  "file_path": "/workspace/main.py",
  "line_number": 10,
  "raw_output": "ImportError: No module named 'requests'",
  "timestamp": "2024-01-15T10:30:00Z",
  "stream_source": "stderr"
}
```

**Monitored Patterns** (REQUIRED):
```python
PATTERNS = {
    r"ImportError: No module named '(\w+)'": "ImportError",
    r"SyntaxError: .* \((.+), line (\d+)\)": "SyntaxError",
    r"AttributeError: .* has no attribute '(\w+)'": "AttributeError",
    r"FAILED tests/.*::(\w+)": "TestFailure",
    r"Coverage: (\d+)%": "CoverageDrop",  # if <90%
}
```

**Failure Behavior**:
- On stream read error: Log WARNING, continue monitoring
- On pattern compile error: Skip pattern, log ERROR
- On callback exception: Log ERROR, continue monitoring

### validator.py - Error Classifier

**Interface**:
```python
class Validator:
    def classify_error(self, event: ErrorEvent) -> Classification:
        """
        MUST classify error and determine intervention need
        
        Args:
            event: ErrorEvent from watchdog
            
        Returns:
            Classification(
                error_type=str,
                severity="LOW"|"MEDIUM"|"HIGH"|"CRITICAL",
                confidence=float,  # 0.0-1.0
                intervention_required=bool,
                suggested_fix=Optional[str]
            )
        """
        
    def should_intervene(self, classification: Classification) -> bool:
        """
        MUST decide if intervention needed based on:
        - Severity threshold
        - Confidence score
        - Repeat count from RecallDB
        - Cooldown period
        """
```

**Example Classification Output**:
```json
{
  "error_type": "ImportError",
  "severity": "HIGH",
  "confidence": 0.95,
  "intervention_required": true,
  "suggested_fix": "pip install requests"
}
```

**Classification Rules**:
- CRITICAL: System crashes, data loss risks → Always intervene
- HIGH: Import errors, syntax errors → Intervene if confidence >0.8
- MEDIUM: Test failures, linting → Intervene if repeated ≥3 times
- LOW: Warnings, deprecations → Log only, no intervention

**Failure Behavior**:
- On classification error: Default to MEDIUM severity
- On RecallDB unavailable: Proceed without history
- On invalid event: Return LOW severity, log WARNING

## 3. Memory & Learning System

### recall_db.py - Persistent Error Memory

**Interface**:
```python
class RecallDB:
    def __init__(self, db_path: str = "cake_recall.db"):
        """
        MUST initialize SQLite with WAL mode
        MUST create tables if not exist
        MUST set up connection pool (max=5)
        """
        
    def record_error(self, signature: str, context: dict) -> None:
        """
        MUST persist error with automatic TTL
        
        Args:
            signature: SHA256 hash of normalized error
            context: Full error context including intervention
            
        Raises:
            DatabaseError: On write failure (MUST retry 3x)
        """
        
    def get_similar_errors(self, signature: str, threshold: float = 0.85) -> List[dict]:
        """
        MUST return errors with similarity ≥ threshold
        Query time MUST be <10ms for 10k records
        """
```

**Database Schema** (REQUIRED):
```sql
-- Main error tracking table
CREATE TABLE error_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_signature TEXT UNIQUE NOT NULL,
    error_type TEXT NOT NULL,
    file_path TEXT,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    occurrence_count INTEGER DEFAULT 1,
    intervention_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    last_intervention TEXT,
    expires_at DATETIME DEFAULT (datetime('now', '+24 hours')),
    INDEX idx_signature (error_signature),
    INDEX idx_expires (expires_at)
);

-- Pattern violations tracking
CREATE TABLE pattern_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,  -- "scope_drift", "unsafe_command", etc.
    details TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    prevented BOOLEAN DEFAULT TRUE
);
```

**Example Error Record**:
```json
{
  "error_signature": "sha256:abc123def456...",
  "error_type": "ImportError",
  "file_path": "/workspace/main.py",
  "first_seen": "2024-01-15T10:30:00Z",
  "last_seen": "2024-01-15T10:35:00Z",
  "occurrence_count": 3,
  "intervention_count": 2,
  "success_count": 1,
  "last_intervention": "Operator (CAKE): Stop. Run pip install requests. See requirements.txt.",
  "expires_at": "2024-01-16T10:30:00Z"
}
```

**Connection Pool Config**:
```python
POOL_CONFIG = {
    "max_connections": 5,
    "timeout": 30.0,
    "check_same_thread": False,
    "isolation_level": None,  # Autocommit mode
}
```

**Failure Behavior**:
- On connection timeout: Wait with exponential backoff
- On lock contention: Retry up to 3 times
- On corruption detected: Switch to in-memory fallback
- On disk full: Rotate oldest entries

### cross_task_knowledge_ledger.py - Learning System

**Interface**:
```python
class KnowledgeLedger:
    def get_intervention_history(self, error_type: str) -> InterventionHistory:
        """
        MUST return successful intervention strategies
        
        Returns:
            InterventionHistory(
                successful_fixes=[str],
                failed_attempts=[str],
                avg_resolution_time=float,
                escalation_patterns=dict
            )
        """
        
    def update_outcome(self, intervention_id: str, success: bool, context: dict) -> None:
        """
        MUST update intervention effectiveness metrics
        
        Args:
            intervention_id: Unique intervention identifier
            success: Whether intervention resolved issue
            context: Full context including time to resolution
        """
```

**Example InterventionHistory**:
```json
{
  "successful_fixes": [
    "Operator (CAKE): Stop. Run pip install requests. See requirements.txt.",
    "Operator (CAKE): Stop. Check virtual environment. Run pip list."
  ],
  "failed_attempts": [
    "Operator (CAKE): Stop. Try pip3 install. Check python version."
  ],
  "avg_resolution_time": 15.5,
  "escalation_patterns": {
    "after_attempts": 3,
    "common_escalation": "missing_system_package"
  }
}
```

## 4. Safety & Control Layer

### pty_shim.py - Command Interceptor

**Interface**:
```python
class PTYShim:
    def intercept_command(self, command: str) -> CommandDecision:
        """
        MUST validate command in <50ms
        
        Returns:
            CommandDecision(
                allowed=bool,
                reason=Optional[str],
                alternative=Optional[str],
                log_entry=dict
            )
        """
        
    def add_to_whitelist(self, pattern: str) -> None:
        """
        MUST add pattern to allowed commands
        MUST persist to config
        """
```

**CommandDecision Structure**:
```python
@dataclass
class CommandDecision:
    allowed: bool
    reason: Optional[str]
    alternative: Optional[str]
    requires_confirmation: bool = False
    log_entry: dict = field(default_factory=dict)
```

**Example CommandDecision**:
```json
{
  "allowed": false,
  "reason": "Force push blocked, fix conflicts properly",
  "alternative": "git push --force-with-lease",
  "requires_confirmation": false,
  "log_entry": {
    "timestamp": "2024-01-15T10:30:00Z",
    "command": "git push --force",
    "user": "claude",
    "session_id": "abc123"
  }
}
```

**Blocked Patterns** (REQUIRED):
```python
BLOCKED_PATTERNS = {
    r"git\s+reset\s+--hard": "Use git stash instead",
    r"git\s+push\s+--force": "Force push blocked, fix conflicts properly",
    r"rm\s+-rf\s+/": "Catastrophic deletion blocked",
    r"chmod\s+777": "Insecure permissions blocked",
    r"sudo\s+": "Elevated privileges not allowed",
    r"docker.*--privileged": "Privileged containers blocked"
}
```

**Audit Log Entry**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "command": "git push --force",
  "decision": "blocked",
  "reason": "Force push blocked",
  "alternative": "git push --force-with-lease",
  "user": "claude",
  "session_id": "abc123"
}
```

**Failure Behavior**:
- On regex error: Block command, log ERROR
- On timeout (>50ms): Allow with WARNING log
- On whitelist conflict: Blocked patterns take precedence

### snapshot_manager.py - State Protection

**Interface**:
```python
class SnapshotManager:
    def create_snapshot(self, label: str, metadata: dict = None) -> str:
        """
        MUST complete in <5 seconds
        
        Returns:
            str: snapshot_id (UUID format)
            
        Raises:
            SnapshotError: On creation failure
        """
        
    def list_snapshots(self, limit: int = 10) -> List[SnapshotInfo]:
        """
        MUST return recent snapshots with metadata
        """
        
    def cleanup_old_snapshots(self, retention_hours: int = 72) -> int:
        """
        MUST remove snapshots older than retention
        MUST preserve snapshots linked to errors
        
        Returns:
            int: Number of snapshots removed
        """
```

**Snapshot Metadata**:
```json
{
  "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
  "label": "pre-force-push",
  "timestamp": "2024-01-15T10:30:00Z",
  "git_commit": "abc123def",
  "branch": "main",
  "dirty_files": ["src/main.py", "tests/test_main.py"],
  "linked_errors": ["error_sig_123", "error_sig_456"],
  "size_bytes": 1048576
}
```

**Garbage Collection Rules**:
- Remove if: age > retention_hours AND not linked to active errors
- Preserve if: linked to unresolved errors OR marked as checkpoint
- Enforce: total size < 1GB (remove oldest first)

## 5. Integration Adapters

### adapter_interface.py - Common Interface

**Interface** (MUST be implemented by all adapters):
```python
class CAKEAdapter(ABC):
    @abstractmethod
    def inject_intervention(self, message: str, context: dict) -> None:
        """
        MUST inject message into active session
        MUST complete within 100ms
        
        Raises:
            AdapterError: On injection failure
        """
        
    @abstractmethod
    def register_hook(self, event: str, callback: Callable) -> None:
        """
        MUST register callback for event
        Events: "pre_execute", "post_execute", "error"
        """
        
    @abstractmethod
    def get_health(self) -> HealthStatus:
        """
        Returns:
            HealthStatus(
                healthy=bool,
                latency_ms=float,
                error_rate=float,
                last_error=Optional[str]
            )
        """
```

**Event Callback Format**:
```python
def pre_execute_callback(context: dict) -> Optional[dict]:
    """
    Args:
        context: {
            "command": str,
            "args": List[str],
            "cwd": str,
            "env": dict
        }
        
    Returns:
        None: Allow execution
        dict: Modified context
        
    Raises:
        BlockedOperationError: Prevent execution
    """
```

**Example Callback Context**:
```json
{
  "command": "git",
  "args": ["push", "--force"],
  "cwd": "/workspace",
  "env": {
    "PATH": "/usr/bin:/bin",
    "USER": "claude"
  }
}
```

## 6. Configuration & Metrics

### cake_config.yaml - Configuration Schema

**Required Fields**:
```yaml
# MUST be present and valid
version: "1.0"
strictness: balanced  # MUST be: minimal|balanced|paranoid

escalation:
  max_strikes: 4      # MUST be integer 1-10
  cooldown_minutes: 5 # MUST be integer 1-60
  human_notification:
    enabled: false
    webhook: ""       # Required if enabled=true

performance:
  max_latency_ms: 300     # MUST be integer 50-1000
  max_memory_mb: 1024     # MUST be integer 512-4096
  
safety:
  require_confirmation: false
  audit_all_commands: true
```

**Optional Fields** (with defaults):
```yaml
# MAY be overridden
database:
  path: "~/.cake/recall.db"
  ttl_hours: 24
  
logging:
  level: "INFO"
  file: "~/.cake/cake.log"
  max_size_mb: 100
  
snapshot:
  retention_hours: 72
  max_size_gb: 1
```

### metrics.py - Observability

**Required Metrics** (Prometheus format):
```python
# Counter metrics
cake_interventions_total = Counter(
    'cake_interventions_total',
    'Total number of interventions',
    ['type', 'severity', 'success']
)

cake_errors_prevented_total = Counter(
    'cake_errors_prevented_total', 
    'Total errors prevented',
    ['error_type']
)

# Histogram metrics  
cake_response_latency_seconds = Histogram(
    'cake_response_latency_seconds',
    'Response latency by component',
    ['component', 'operation'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# Gauge metrics
cake_voice_similarity_score = Gauge(
    'cake_voice_similarity_score',
    'Current voice similarity score',
    ['message_type']
)
```

**Export Endpoint**: `http://localhost:9090/metrics`

**Metric SLOs** (Service Level Objectives):
- `cake_response_latency_seconds{p99}` < 0.5
- `cake_errors_prevented_total` > 0 (daily)
- `cake_voice_similarity_score` ≥ 0.90