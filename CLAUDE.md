# CAKE (Claude Autonomy Kit Engine) Development Assistant Memory

## Project Overview
CAKE is a deterministic intervention system that monitors LLM operations, prevents known failure patterns, and enforces safety guardrails without human escalation. It acts as an autonomous "operator" that clones Dustin's intervention style to supervise any LLM.

## Project Location & Setup
- **Primary Directory**: `/Users/dustinkirby/Documents/GitHub/CAKE`
- **GitHub Repository**: `ZeroSumQuant/CAKE`
- **Language**: Python 3.11+
- **Architecture**: Single-process, component-based system (no microservices)
- **Configuration**: `cake_config.yaml` with hot-reload support

## Critical Design Principles
1. **Zero-Escalation Autonomy**: Resolve ALL failures without paging humans
2. **Deterministic Interventions**: Template-driven, voice-consistent messages
3. **Pattern Memory**: Learn from repeated errors to prevent recurrence
4. **Safe-by-Default**: Block dangerous operations before execution
5. **Hot-Reloadable**: Configuration changes without service restart

## Core Components (All Required)
- **CakeController**: Central state machine orchestrator
- **Operator**: Intervention message generator (MUST match Dustin's voice ≥90%)
- **RecallDB**: Error pattern memory store with SQLite backend
- **PTYShim**: Command interceptor for safety
- **Validator**: Error classifier (severity levels: LOW/MEDIUM/HIGH/CRITICAL)
- **Watchdog**: Stream monitor for error detection

## Development Workflow
1. **Start each session with**:
   ```bash
   cd /Users/dustinkirby/Documents/GitHub/CAKE
   pwd && git status && git branch -a
   ```

2. **Before ANY implementation**:
   - Review the appropriate implementation guide in project root
   - Check `cake-done-checklist-v2.md` for component status
   - Use scripts from `cake-scripts-suite.md` to accelerate development

3. **Testing Requirements** (STRICT):
   - ≥90% test coverage (CI enforced)
   - Unit tests for ALL public methods
   - Integration tests for component interactions
   - Performance tests must meet benchmarks:
     - Detection latency: <100ms
     - Command validation: <50ms
     - RecallDB query: <10ms for 10k records
     - 100 messages in ≤0.3s

4. **Code Quality Gates** (Must Pass):
   ```bash
   black . && isort . && flake8 && mypy . && pytest --cov=cake --cov-report=term-missing
   ```

5. **Security Checks**:
   ```bash
   bandit -r cake/ -ll && safety check
   ```

## Operator Voice Requirements (CRITICAL)
The Operator component MUST match Dustin's intervention style:
- Format: `"Operator (CAKE): Stop. {action}. {reference}."`
- Approved verbs ONLY: Run, Check, Fix, Try, See
- Maximum 3 sentences per intervention
- ≥90% voice similarity required (measured by tests)
- Direct, imperative, no explanations

## Safety Rules (NEVER COMPROMISE)
1. PTYShim MUST block these commands:
   - `git push --force`
   - `rm -rf /`
   - `sudo` commands (unless explicitly allowed)
   - Any command matching dangerous patterns

2. Always create snapshots before risky operations
3. Validate ALL commands in <50ms
4. Log ALL blocked commands with full context

## Implementation Status Tracking
- Check `cake-done-checklist-v2.md` for component ownership
- Update status immediately when claiming a component
- Components are currently UNASSIGNED - coordinate ownership

## Performance Benchmarks (Required)
- Startup time: <2 seconds
- Memory usage: <200MB baseline
- Detection latency: <100ms
- Command validation: <50ms
- RecallDB operations: <10ms
- Message generation: 100 messages in ≤0.3s

## Deployment Targets
- Local development (primary)
- Docker containers
- Kubernetes (with provided manifests)
- Configuration via environment variables or `cake_config.yaml`

## Documentation Requirements
- Update implementation guides when changing architecture
- Keep `cake-done-checklist-v2.md` current
- Document ALL design decisions in ADRs
- Maintain API documentation in docstrings

## Git Workflow
1. Branch naming: `feature/component-name` or `fix/issue-description`
2. Conventional commits: `feat(operator): add voice similarity check`
3. PR required for main branch
4. Must pass ALL CI checks before merge

## Testing Philosophy
- Test EVERYTHING that can fail
- Mock external dependencies
- Use fixtures for consistent test data
- Performance tests are NOT optional
- 8-hour autonomous operation test before release

## Common Pitfalls to Avoid
1. Don't add microservices - everything runs in-process
2. Don't skip performance tests - they're required
3. Don't modify Operator voice without similarity testing
4. Don't bypass PTYShim for "convenience"
5. Don't ignore RecallDB TTL management

## Scripts Available
Review `cake-scripts-suite.md` for helper scripts:
- Component generators
- Test scaffolding
- Benchmark runners
- Integration test suites
- Deployment validators

## Success Metrics
- Zero human escalations in 8-hour test
- >85% error prevention rate
- ≥90% voice similarity
- ALL performance benchmarks met
- 100% of dangerous commands blocked

---
Remember: CAKE's goal is complete autonomy. Every decision should support the vision of an LLM that never needs human intervention.