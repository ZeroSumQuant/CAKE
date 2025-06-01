# CAKE "DONE" Checklist - Ship Criteria

**This is the authoritative ship criteria for CAKE. Every item MUST be checked before release.**

## 🎯 North Star
Ship a deterministic "Operator-clone of Dustin" that supervises any LLM, self-heals, and never pages Dustin.

## ✅ Core Functionality (MUST be complete)

### 🟢 Operator Clone Live
**Complete when**:
- [ ] `test_operator_voice.py` passes (100%)
- [ ] Voice similarity ≥90% on all messages
- [ ] Zero randomness in message generation
- [ ] Watchdog detects errors in <100ms
- [ ] Interventions prevent >85% of failures

**Evidence Required**:
```bash
# Test output showing pass
poetry run pytest tests/unit/test_operator_voice.py -v
# Expected: 25 passed in 0.34s

# Voice similarity report
poetry run cake test voice-similarity --threshold=0.9
# Expected: 100/100 messages pass with avg similarity 0.94
```

### 🟢 Guard-Rails Configurable  
**Complete when**:
- [ ] All safety rules in `cake_config.yaml`
- [ ] Hot-reload confirmed working
- [ ] Config changes apply in <1s
- [ ] No hardcoded safety logic
- [ ] Domain overrides functional

**Evidence Required**:
```bash
# Hot reload test
echo "strictness: paranoid" >> cake_config.yaml
sleep 2
poetry run cake config show --key=strictness
# Expected: "strictness: paranoid"

# Verify no hardcoded safety
grep -r "blocked_commands\|git.*force" cake/ --include="*.py"
# Expected: No results (all in config)
```

### 🟢 Repeat-Error Memory
**Complete when**:
- [ ] RecallDB stores all error signatures
- [ ] Detects ≥3 identical failures
- [ ] Auto-intervention triggers correctly
- [ ] 24-hour TTL enforced
- [ ] Query performance <10ms

**Evidence Required**:
```bash
# Database stats
poetry run cake db stats --table=error_memory
# Expected:
# Total records: 1,247
# Unique signatures: 89
# Avg query time: 4.2ms
# Oldest entry: 23h 45m ago

# Performance test
poetry run pytest tests/integration/test_recall_memory.py::test_query_performance -v
# Expected: PASSED - Query time: 4.2ms < 10ms
```

### 🟢 Rollback Reliable
**Complete when**:
- [ ] Snapshots created before risky ops
- [ ] `cake rollback` restores in <5s
- [ ] Git stash integration works
- [ ] Work in progress preserved
- [ ] Metadata tracking accurate

**Evidence Required**:
```bash
# Rollback test
poetry run cake snapshot create --label=test-rollback
echo "break everything" > main.py
poetry run cake rollback --latest
git status

# Expected output:
# Snapshot created: 550e8400-e29b-41d4-a716-446655440000
# Rolling back to snapshot...
# Rollback complete in 3.2s
# On branch main
# nothing to commit, working tree clean
```

## ✅ Quality & Performance (MUST meet thresholds)

### 🟢 CI All Green
**Complete when ALL pass with zero errors/warnings**:
```yaml
- black: ✓ (formatted)
- isort: ✓ (imports sorted)  
- flake8: ✓ (zero violations)
- mypy: ✓ (type checking passes)
- bandit: ✓ (no security issues)
- safety: ✓ (no vulnerable deps)
- pytest: ✓ (all tests pass)
- coverage: ✓ (≥90%)
```

**Evidence Required**:
```bash
# Run all checks
poetry run make lint
# Expected: All checks passed (exit code 0)

poetry run make test
# Expected: 847 passed, coverage: 93.2%

# CI status badge
curl https://api.github.com/repos/your-org/cake/commits/main/status
# Expected: "state": "success"
```

### 🟢 Performance Benchmarks
**Complete when**:
- [ ] 100 messages processed in ≤0.3s
- [ ] Command validation <50ms (p99)
- [ ] Database queries <10ms (p99)
- [ ] Memory usage <1GB (24 hours)
- [ ] CPU usage <50% (sustained)

**Evidence Required**:
```bash
# Run benchmarks
poetry run pytest tests/perf/ --benchmark-only
# Expected output:
# test_100_message_latency: 0.287s ✓
# test_command_validation: 0.042s ✓
# test_database_query: 0.008s ✓
# test_snapshot_creation: 3.891s ✓
# All benchmarks PASSED

# 24-hour test results
poetry run cake benchmark --duration=24h --report
# Expected: benchmark_report_24h.json showing all metrics in range
```

### 🟢 Metrics Flowing
**Complete when**:
- [ ] Prometheus endpoint serves metrics
- [ ] Grafana dashboard loads correctly
- [ ] All counters incrementing
- [ ] No metric gaps >1 minute
- [ ] Alerts configured and firing

**Evidence Required**:
```bash
# Check metrics
curl -s http://localhost:9090/metrics | grep -c "cake_"
# Expected: 25 (all metrics present)

# Verify incrementing
curl -s http://localhost:9090/metrics | grep cake_interventions_total
sleep 300  # Wait 5 minutes
curl -s http://localhost:9090/metrics | grep cake_interventions_total
# Expected: Counter increased

# Alert test
poetry run cake test alerts
# Expected: Test alert fired and received
```

## ✅ User Experience (MUST work perfectly)

### 🟢 Quick-Start Passes
**Complete when this exact sequence works on fresh Ubuntu 22.04**:
```bash
# Fresh system test
git clone https://github.com/your-org/cake.git
cd cake
poetry install
poetry run cake demo --fail-seed

# Expected output:
# ✅ Error injected: ImportError in demo.py
# ✅ CAKE detected error in 47ms
# ✅ Intervention: "Operator (CAKE): Stop. Run pip install requests. See requirements.txt."
# ✅ Error resolved automatically
# ✅ Demo complete (time: 52s)
```

**Evidence Required**:
- Screenshot of successful demo run
- Exit code 0
- Time < 60 seconds

### 🟢 Zero-Escalation Autonomy  
**Complete when** (test file: `test_zero_escalation_flow.py`):
- [ ] Import errors: Fixed via pip install
- [ ] Test failures: Fixed with guidance
- [ ] CI bypasses: Blocked and rolled back
- [ ] Feature creep: Detected and redirected
- [ ] 8-hour run: Zero human pages

**Evidence Required**:
```bash
# Run 8-hour test
poetry run pytest tests/integration/test_zero_escalation_flow.py::test_8_hour_autonomous -v

# Expected test output:
# test_8_hour_autonomous PASSED [100%]
# 
# Test Summary:
# Duration: 8h 0m 12s
# Total errors: 347
# Interventions: 342
# Resolved: 342 (98.6%)
# Escalations: 0
# System uptime: 100%
```

**Test Report Required** (`test_results/8_hour_autonomous.json`):
```json
{
  "test_duration_hours": 8.003,
  "total_errors_injected": 347,
  "interventions_delivered": 342,
  "errors_resolved": 342,
  "resolution_rate": 0.986,
  "human_escalations": 0,
  "system_crashes": 0,
  "memory_peak_mb": 743,
  "verdict": "PASS"
}
```

### 🟢 Dustin-Tone Guaranteed
**Complete when**:
- [ ] Sample messages match reference ≥90%
- [ ] Max 3 sentences enforced
- [ ] Approved verbs only used
- [ ] No apologies/explanations
- [ ] Style tests all pass

**Evidence Required**:
```bash
# Voice test with 100 samples
poetry run cake test voice --samples=100 --verbose

# Expected output:
# Testing voice similarity...
# Sample 1: 0.92 ✓ "Operator (CAKE): Stop. Run tests. See output."
# Sample 2: 0.94 ✓ "Operator (CAKE): Stop. Fix import. Check line 10."
# ...
# Sample 100: 0.91 ✓ "Operator (CAKE): Stop. Try git pull. See conflicts."
# 
# Results: 100/100 passed
# Average similarity: 0.93
# Min similarity: 0.90
# All samples ≤3 sentences ✓
# Only approved verbs used ✓
```

## ✅ Integration Support (MUST work with all)

### 🟢 Adapter Coverage
**Complete when each adapter**:
- [ ] Claude Code: Injection works
- [ ] Anthropic API: Streaming works
- [ ] LUCA RPC: Bidirectional comm works
- [ ] Hot-swap: No message loss
- [ ] Fallback: Graceful degradation

**Evidence Required**:
```bash
# Test all adapters
poetry run cake test adapters --all --verbose

# Expected output:
# Testing Claude Code adapter...
#   Connection: OK
#   Injection test: PASSED
#   Round-trip time: 23ms
#   
# Testing Anthropic API adapter...
#   Connection: OK
#   Streaming test: PASSED
#   Message delivery: 100/100
#   
# Testing LUCA RPC adapter...
#   Connection: OK
#   Bidirectional test: PASSED
#   Latency: 15ms
#   
# Hot-swap test: PASSED (0 messages lost)
# Fallback test: PASSED (degraded gracefully)
# 
# All adapter tests PASSED
```

### 🟢 Production Ready
**Complete when**:
- [ ] Install script works on Ubuntu/macOS
- [ ] Docker image <500MB
- [ ] K8s manifests deploy successfully
- [ ] Backup/restore cycle tested
- [ ] Security scan shows zero high/critical

**Evidence Required**:
```bash
# Install test on fresh VM
./scripts/install.sh
# Expected: Exit code 0, CAKE running

# Docker image size
docker images cake:latest
# Expected: SIZE < 500MB

# K8s deployment
kubectl apply -f k8s/ -n cake-test
kubectl wait --for=condition=ready pod -l app=cake -n cake-test
# Expected: deployment/cake-controller condition met

# Security scan
poetry run bandit -r cake/ -f json -o security_scan.json
# Expected: "results": []

poetry run safety check --json
# Expected: "vulnerabilities": []
```

## 📋 Final Release Gate

### Required Artifacts (MUST exist)
```
cake/
├── README.md (with architecture diagram) ✓
├── LICENSE (MIT or Apache 2.0) ✓
├── cake_config.yaml.example ✓
├── requirements.txt / pyproject.toml ✓
├── Dockerfile (<500MB image) ✓
├── k8s/
│   ├── deployment.yaml ✓
│   └── service.yaml ✓
├── scripts/
│   ├── install.sh (tested on Ubuntu/macOS) ✓
│   ├── benchmark.py ✓
│   └── check_health.py ✓
├── tests/
│   ├── unit/ (≥50 test files) ✓
│   ├── integration/ (≥10 test files) ✓
│   └── perf/ (≥5 test files) ✓
├── docs/
│   ├── architecture.md ✓
│   ├── api_reference.md ✓
│   ├── deployment.md ✓
│   └── troubleshooting.md ✓
└── grafana/
    └── cake-dashboard.json ✓
```

**Evidence Required**: 
```bash
# Verify all files
find . -name "*.md" -o -name "*.yaml" -o -name "*.json" | wc -l
# Expected: ≥25 files

# Verify test count
find tests/ -name "test_*.py" | wc -l
# Expected: ≥65 test files

# Verify documentation
wc -l docs/*.md
# Expected: Each file >100 lines
```

### Final Commands (MUST all succeed)
```bash
# 1. Clean install
rm -rf ~/.cake venv/
./scripts/install.sh
# Expected: Exit 0, no errors

# 2. Run tests
poetry run pytest --cov=cake --cov-fail-under=90
# Expected: All passed, coverage ≥90%

# 3. Run benchmarks  
poetry run cake benchmark --all
# Expected: All benchmarks within limits

# 4. Run 8-hour test
poetry run cake test --autonomous --duration=8h
# Expected: Zero escalations

# 5. Build artifacts
docker build -t cake:latest .
poetry build
# Expected: cake-1.0.0.tar.gz created

# 6. Security scan
poetry run bandit -r cake/
poetry run safety check
# Expected: No issues found
```

### Documentation Updates Required
**Docs updated = These specific files with these specific changes:**

1. **README.md**: 
   - [ ] Architecture diagram present
   - [ ] Quick start section matches actual commands
   - [ ] Performance numbers updated from benchmarks

2. **CHANGELOG.md**:
   - [ ] Version 1.0.0 entry complete
   - [ ] All breaking changes documented
   - [ ] Migration guide included

3. **docs/api_reference.md**:
   - [ ] All public methods documented
   - [ ] Examples for each method
   - [ ] Return types specified

4. **docs/deployment.md**:
   - [ ] Tested deployment commands
   - [ ] Troubleshooting section updated
   - [ ] Performance tuning guide added

## 🚀 Ship Decision

### If Not Done (Remediation Required)

**For each unchecked item above**:
1. Create GitHub issue with "[BLOCKER]" prefix
2. Assign to component owner
3. Set deadline: 24 hours for critical, 48 hours for others
4. Daily standup on blockers until resolved

**Escalation Path**:
- Day 1: Component owner
- Day 2: Tech lead
- Day 3: CTO decision on ship/delay

### Approval Process

**Reviews Required** (with evidence):
1. **Code Review**: Approved via PR #___ by @___
2. **Security Review**: Approved via issue #___ by security team
3. **Performance Review**: Benchmarks approved by @___
4. **8-Hour Test**: Passed on date ___ (link to results)
5. **Documentation Review**: Approved by @___

**Final Approval**: 
```
CTO Sign-off: _________________ Date: _______
```

**Ship Status**: 
```python
if all_items_checked and all_reviews_approved:
    status = "READY TO SHIP 🎉"
    next_action = "Tag release, deploy to production"
else:
    status = "NOT READY ❌"
    blockers = [item for item in checklist if not item.checked]
    next_action = f"Fix {len(blockers)} remaining items"
```

## 📊 Post-Ship Success Metrics

### Day 1
- Interventions delivered: >10 ✓ Actual: ___
- Errors prevented: >5 ✓ Actual: ___
- Escalations to human: 0 ✓ Actual: ___
- Uptime: 100% ✓ Actual: ___%

### Week 1  
- Developer adoption: >50% ✓ Actual: ___%
- Error prevention rate: >85% ✓ Actual: ___%
- False positive rate: <5% ✓ Actual: ___%
- Performance SLAs: Met ✓ Status: ___
- User satisfaction: >4/5 ✓ Actual: ___/5

### Month 1
- Dustin interruptions: -90% ✓ Actual: ___%
- Development velocity: +20% ✓ Actual: ___%
- System stability: 99.9% ✓ Actual: ___%
- ROI demonstrated: Yes ✓ Evidence: ___

---

**Remember**: Every checkmark must be verifiable with a command or test. No manual verification allowed. Ship only when truly DONE.