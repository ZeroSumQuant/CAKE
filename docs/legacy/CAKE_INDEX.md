# CAKE Project Index

## 🔴 MANDATORY: START EVERY SESSION WITH WATCHDOG 🔴
```bash
cd /Users/dustinkirby/Documents/GitHub/CAKE
./start_watchdog.sh  # THIS IS MANDATORY - DO NOT SKIP!
```

**The Claude Watchdog will:**
- Run silently in background
- Monitor for common Claude mistakes
- Create CLAUDE_STOP.txt files when interventions needed
- Auto-cleanup after interventions are read

**Common interventions it catches:**
1. Running bash scripts with Python
2. Creating multiple fix scripts instead of one comprehensive solution
3. Missing hidden directories (.venv)
4. Using 'ls' without -la flag

## 🚨 Claude Self-Monitoring System (2025-06-02)
- **claude_monitor.py**: Real-time intervention system that catches common mistakes
- **CLAUDE_INTERVENTIONS.md**: Quick reference for intervention patterns
- **Updated CLAUDE.md**: Added STOP patterns section for self-monitoring

### Key Interventions:
1. Hidden files (.venv) - Use `ls -la` not LS tool
2. Script execution - Check interpreter with `file` first  
3. Syntax fixes - Collect ALL errors before fixing
4. Path navigation - Use absolute paths
5. Tool efficiency - Batch similar operations

## Quick Start Guide

**MANDATORY First Step:**
```bash
./start_watchdog.sh  # MUST run before ANY work begins!
```

**Core Flow:**
Watchdog detects errors → CakeController orchestrates → Operator intervenes → RecallDB remembers

**Start Here:**
- Claude monitoring: claude_watchdog.py (RUNS IN BACKGROUND)
- System orchestration: cake/core/cake_controller.py
- Intervention logic: cake/components/operator.py  
- Error memory: cake/components/recall_db.py
- Safety validation: cake/core/pty_shim.py

**Key Relationships:**
- Claude Watchdog monitors for Claude-specific mistakes in real-time
- CakeController uses all components to manage task execution
- Operator creates intervention messages matching Dustin's voice
- RecallDB stores error patterns to prevent repeat failures
- PTYShim intercepts dangerous commands before execution
- Watchdog monitors streams for real-time error detection

**Common Tasks:**
- Add new intervention type: operator.py:34-49 (InterventionType enum)
- Create intervention message: operator.py:69-109 (templates)
- Add dangerous command pattern: rule_creator.py:85-94
- Implement new error classifier: semantic_error_classifier.py:141
- Modify voice corpus: voice_similarity_gate.py:133-143

**Missing Pieces:**
- Digital Dustin I/O Layer (GitHub issue #42) - stream watching & keyboard control

## Recent Fixes (2025-06-02)

### Syntax Error Resolution
- **Issue**: 33 docstring syntax errors (E999) across multiple files
- **Pattern**: Code immediately after closing `"""` on same line
- **Solution**: Created fix_comprehensive_syntax_errors.py that:
  - Handles multiple patterns: `"""code`, `"""(`, `"""assignment`
  - Fixed all 33 errors in batch
  - Maintains proper indentation
- **Status**: ✅ All syntax errors resolved
- **Script**: fix_comprehensive_syntax_errors.py

---

## A

Adapters
- cake/adapters/cake_adapter.py:67-373
  - initialization:70-117
  - intervention detection:119-157
  - repeat error checking:159-175
  - CI status updates:177-193
  - linter status handling:195-209
  - feature creep detection:321-338
- cake/adapters/cake_integration.py:42-297
  - task lifecycle:101-142
  - stage processing:144-201
  - task finalization:202-228
- cake/adapters/claude_orchestration.py:987-1819
  - prompt templates:189-658
  - response analysis:987-1342
  - context enhancement:758-966

AdaptiveConfidenceEngine
- cake/components/adaptive_confidence_engine.py:368-917
  - confidence pattern learning:732-793
  - Bayesian updates:201-259
  - decision recording:503-578
  - pattern persistence:857-877
See also: Confidence scoring, Machine learning

Analyzer
- InterventionAnalyzer
  - cake/components/operator.py:453-764
  - situation analysis:453-502
  - error pattern detection:504-543
  - test skip detection:544-599
  - coverage drop detection:601-616
- SemanticErrorClassifier
  - cake/components/semantic_error_classifier.py:1015-1650
  - feature extraction:331-366
  - pattern matching:413-431
  - semantic analysis:1019-1213
- ResponseAnalyzer
  - cake/adapters/claude_orchestration.py:987-1342
  - quality assessment:1000-1058
  - completeness checking:1060-1099
  - actionability scoring:1139-1177

Architecture
- docs/guides/cake-architecture-v2.md
- docs/guides/cake-components-v2.md
- CLAUDE.md:13-18
See also: Design patterns, System architecture

## B

Bad Claude Simulator
- tests/bad_claude_simulator/
- README.md
- bad_claude.py
- scenarios.py
- test_scenarios/
See also: Testing, Validation

Bandit
- pyproject.toml
See also: Security, Validation

BayesianConfidenceUpdater
- cake/components/adaptive_confidence_engine.py:201-259
  - prior/posterior calculation:216-247
  - outcome weighting:248-259
See also: Machine learning, Probability

Black
- pyproject.toml
- line length: 100
See also: Code quality, Linting

## C

CAKE_INDEX.md - This file

CakeController
- cake/core/cake_controller.py:62-307
  - orchestrator:62-87
  - task execution:158-209
  - intervention checking:210-227
  - stage execution:228-238
  - validation:260-264
See also: Controllers, State machine

CakeIntegration
- cake/adapters/cake_integration.py:42-297
  - integration:42-100
  - task management:101-142
  - stage processing:144-201
See also: Adapters, Integration

CLAUDE.md
- development principles:13-18
- voice requirements:60-66
- safety rules:68-78
- testing philosophy:110-115
See also: Documentation, Guidelines

Claude Watchdog System
- claude_watchdog.py - Background monitor for Claude mistakes
- start_watchdog.sh - MANDATORY startup script
- stop_watchdog.sh - Cleanup script
- WATCHDOG_README.md - Full documentation
- CLAUDE_INTERVENTIONS.md - Intervention patterns
- Monitors:
  - Multiple fix scripts creation
  - Wrong interpreter usage (python3 on .sh files)
  - Hidden directory misses (.venv)
  - Bare ls commands
See also: Monitoring, Interventions, Real-time feedback

Commands
- dangerous patterns
  - cake/utils/rule_creator.py:85-94
- safe commands
  - cake/utils/rule_creator.py:112-121
- command validation
  - cake/utils/rule_creator.py:195-235
- PTY interception
  - cake/core/pty_shim.py
See also: Safety, Validation

Components
- cake/components/operator.py
- cake/components/recall_db.py
- cake/components/validator.py
- cake/components/semantic_error_classifier.py
- cake/components/adaptive_confidence_engine.py
- cake/components/snapshot_manager.py
- cake/components/voice_similarity_gate.py

Configuration
- cake_config.yaml
- CLAUDE.md:18
See also: Settings, Deployment

Confidence
- cake/components/adaptive_confidence_engine.py:201-259
  - pattern adaptation:430-509
  - feature extraction:105-180
  - historical learning:732-793
See also: AdaptiveConfidenceEngine, Machine learning

Controllers
- cake/core/cake_controller.py:62-307
- cake/core/stage_router.py
See also: Orchestration, State machine

Convergence
- cake/components/validator.py:602-817
  - requirement extraction:95-298
  - confidence calculation:500-533
  - gap analysis:584-600
See also: Validation, Requirements

## D

Database
- RecallDB schema
  - cake/components/recall_db.py:101-196
  - error records:107-120
  - pattern violations:122-133
  - command history:135-145
- Outcome database
  - cake/components/adaptive_confidence_engine.py:380-395
- Knowledge ledger
  - cake/utils/cross_task_knowledge_ledger.py
See also: Persistence, SQLite

Dependencies
- requirements.txt:1-11 (runtime)
- requirements.txt:12-14 (ML/data science)
- requirements.txt:19-27 (testing)
- requirements.txt:29-39 (development)
See also: Installation, Setup

Deployment
- docs/guides/cake-deployment-v2.md
See also: Installation, Production

Design Patterns
- cake/core/cake_controller.py (state machine)
- cake/core/strategist.py (strategy pattern)
See also: Architecture, Patterns

Documentation
- docs/guides/
- docs/handoff/
- docs/specifications/
See also: CLAUDE.md, README files

## E

Error Classification
- cake/components/semantic_error_classifier.py:1015-1650
  - error patterns:141-314
  - feature extraction:331-366
  - signature database:773-1012
See also: SemanticErrorClassifier, Pattern matching

Error Handling
- cake/adapters/cake_adapter.py:159-175
- cake/components/recall_db.py:197-241
- cake/components/semantic_error_classifier.py:413-431
See also: RecallDB, Interventions

EscalationDecider
- cake/core/escalation_decider.py
See also: Interventions, Autonomy

## F

Feature Extraction
- cake/components/semantic_error_classifier.py:331-366
- cake/components/adaptive_confidence_engine.py:105-180
  - pattern signatures:150-179
See also: Machine learning, Pattern matching

Flake8
- .flake8
- line length: 100
See also: Linting, Code quality

## G

Git Integration
- cake/components/snapshot_manager.py:64-461
  - stash operations:102-127
  - rollback functionality:129-194
See also: Version control, Snapshots

Guidelines
- CLAUDE.md:20-44 (development)
- CLAUDE.md:46-54 (git workflow)
- CLAUDE.md:45 (testing)
- CLAUDE.md:60-66 (voice requirements)
See also: Best practices, Standards

## H

Handoff Documentation
- docs/handoff/
See also: Documentation, Workflow

Hash Functions
- MD5 (IDs only)
- usedforsecurity=False
See also: Security, Identifiers

Hooks
- cake/adapters/cake_adapter.py:282-287 (pre-message)
- cake/adapters/cake_adapter.py:289-294 (post-message)
- cake/adapters/cake_adapter.py:351-371 (execution)
See also: Integration, Callbacks

## I

Implementation Status
- cake/core/cake_controller.py:122-125
  - ✅ Watchdog, PTYShim, SnapshotManager initialized
- cake/utils/info_fetcher.py:71
  - abstract search() method (intentional)
- Mock classes
  - models.py:29-62 (SQLModel mocks)
  - rate_limiter.py:28-34 (Redis mocks)
- GitHub issue #42 (Digital Dustin I/O Layer)
See also: Architecture, Integration

Imports
- TYPE_CHECKING blocks
See also: Dependencies, Python

InfoFetcher
- cake/utils/info_fetcher.py
  - documentation search:117-285
  - Stack Overflow API:286-365
  - GitHub code search:366-438
See also: Research, External APIs

Installation
- .venv/
- requirements.txt
- scripts/setup/
See also: Dependencies, Setup

Integration
- cake/adapters/
- cake/mcp_servers/
See also: Adapters, Hooks

Interventions
- cake/components/operator.py:34-49 (types enum)
- cake/components/operator.py:69-109 (templates)
- cake/components/operator.py:131-179 (builder)
- cake/components/operator.py:453-764 (analyzer)
See also: Operator, Messages

isort
- pyproject.toml
- profile: black
See also: Code quality, Imports

## J

JSON
- Multiple locations
See also: Serialization, Data formats

## K

Knowledge Management
- cake/utils/cross_task_knowledge_ledger.py
See also: Learning, Memory

## L

Learning
- cake/components/adaptive_confidence_engine.py
- cake/components/semantic_error_classifier.py
See also: AdaptiveConfidenceEngine, Patterns

Linting
- scripts/validation/cake-lint.sh:180-418
- scripts/validation/cake-pre-commit.sh
See also: Code quality, Validation

Logging
- All Python files
See also: Debugging, Monitoring

## M

Machine Learning
- Scikit-learn
- TF-IDF vectorization
- Bayesian inference
See also: Learning, Patterns

Memory
- cake/components/recall_db.py
  - 24-hour TTL:197-241
  - pattern violations:393-421
  - command history:423-457
See also: Persistence, Database

Messages
- cake/components/operator.py:69-109
- cake/components/voice_similarity_gate.py
See also: Interventions, Voice

Metrics
- cake/components/adaptive_confidence_engine.py:293-367
See also: Monitoring, Performance

Models
- cake/utils/models.py
See also: Database, Types

Monitoring
- cake/adapters/cake_adapter.py:265-280
- Prometheus port 9090
See also: Metrics, Observability

mypy
- pyproject.toml
See also: Types, Validation

## N

NetworkX
- cake/core/stage_router.py
See also: Algorithms, Routing

## O

Operator
- cake/components/operator.py
  - message builder:131-179
  - template system:69-109
  - voice requirements:59-66
  - intervention types:34-49
See also: Interventions, Voice

Orchestration
- cake/core/cake_controller.py
- cake/core/stage_router.py
- cake/adapters/claude_orchestration.py
See also: Controllers, Workflow

## P

Patterns
- cake/components/semantic_error_classifier.py:141-314 (error)
- cake/components/operator.py:665-701 (anti-patterns)
- cake/components/adaptive_confidence_engine.py:46-73 (confidence)
See also: Design patterns, Machine learning

Performance
- CLAUDE.md:84-91
- Detection latency: <100ms
- Command validation: <50ms
- RecallDB query: <10ms
- Message generation: ≤0.3s/100 msgs
See also: Metrics, Requirements

Persistence
- SQLite databases
- Pickle serialization
- JSON storage
See also: Database, Storage

Production
- docs/guides/
- Prometheus metrics
See also: Deployment, Monitoring

Prompts
- cake/adapters/claude_orchestration.py:102-757
  - context enhancement:758-966
  - response analysis:987-1342
See also: Templates, Claude

PTYShim
- cake/core/pty_shim.py
- <50ms response requirement
See also: Safety, Commands

pytest
- pyproject.toml
- tests/
- coverage: ≥90%
See also: Testing, Quality

Python
- version: 3.11+
- .venv/
See also: Dependencies, Installation

## Q

Quality
- scripts/validation/
- coverage: ≥90%
- CLAUDE.md:84-91
See also: Testing, Validation

## R

RateLimiter
- cake/utils/rate_limiter.py
See also: Performance, APIs

RecallDB
- cake/components/recall_db.py
  - error memory:197-241
  - pattern tracking:393-421
  - command history:423-457
  - 24-hour TTL
See also: Memory, Database

Requirements
- cake/components/validator.py:95-298 (extraction)
- cake/components/validator.py:331-399 (validation)
See also: Validation, Testing

ResponseAnalyzer
- cake/adapters/claude_orchestration.py:987-1342
  - quality metrics:1000-1058
  - data extraction:1189-1228
  - issue identification:1312-1341
See also: Analysis, Claude

Routing
- cake/core/stage_router.py
See also: Workflow, State machine

RuleCreator
- cake/utils/rule_creator.py
  - automation rules:237-299
  - pattern proposals:301-368
  - validation:131-193
See also: Automation, Patterns

## S

Safety
- cake/utils/rule_creator.py:195-235 (validation)
- cake/utils/rule_creator.py:85-94 (dangerous patterns)
- cake/utils/rule_creator.py:112-121 (safe commands)
- cake/core/pty_shim.py
See also: Security, Validation

Scripts
- scripts/validation/
- scripts/setup/
- scripts/components/
See also: Tools, Automation

Security
- Bandit scanner
- MD5 (ID generation only)
- Pickle (trusted sources only)
See also: Safety, Validation

SemanticErrorClassifier
- cake/components/semantic_error_classifier.py:1015-1650
  - feature extraction:331-366
  - pattern database:773-1012
See also: Error classification, NLP

Serialization
- JSON (configuration)
- Pickle (ML models)
- SQLite (structured storage)
See also: Persistence, Storage

Setup
- scripts/setup/cake-setup-dev.sh
- .venv/
- requirements.txt
See also: Installation, Configuration

Snapshots
- cake/components/snapshot_manager.py
  - git integration:64-127
  - auto-snapshots:211-231
  - rollback:129-194
See also: Git, Version control

SQLite
- cake/components/recall_db.py
  - connection pooling:72-100
  - schema definitions:101-196
See also: Database, Storage

StageRouter
- cake/core/stage_router.py
See also: Workflow, Controllers

State Machine
- cake/core/cake_controller.py
- MONITORING → DETECTING → INTERVENING → RECOVERING → ESCALATING
See also: Architecture, Workflow

Storage
- SQLite databases
- ML model files
- Git snapshots
See also: Database, Persistence

Strategist
- cake/core/strategist.py
See also: Controllers, Decisions

## T

TaskConvergenceValidator
- cake/components/validator.py:602-817
  - convergence validation:612-644
  - report generation:646-731
  - gap analysis:584-600
See also: Validation, Requirements

Templates
- cake/components/operator.py:69-109
- cake/adapters/claude_orchestration.py:189-658
See also: Messages, Prompts

Testing
- tests/unit/
- tests/integration/
- tests/bad_claude_simulator/
  - scenarios.py
  - bad_claude.py
  - test_scenarios/
- coverage: ≥90%
- 8-hour autonomous test
See also: pytest, Validation

TODO Tracking
- Search codebase
See also: Documentation, Planning

Tools
- scripts/validation/
- scripts/setup/
- scripts/components/
See also: Scripts, Automation

TRRDEVS
- Think (stage 1)
- Research (stage 2)
- Reflect (stage 3)
- Decide (stage 4)
- Execute (stage 5)
- Validate (stage 6)
- Solidify (stage 7)
See also: Workflow, Stages

Types
- All Python files
- mypy validation
- Pydantic models
See also: mypy, Validation

## U

Utils
- cake/utils/cross_task_knowledge_ledger.py
- cake/utils/info_fetcher.py
- cake/utils/models.py
- cake/utils/rate_limiter.py
- cake/utils/rule_creator.py

## V

Validation
- cake/components/validator.py
- cake/utils/rule_creator.py
- scripts/validation/
See also: Testing, Quality

Validator
- cake/components/validator.py
  - requirement extraction:95-298
  - convergence checking:612-644
  - confidence calculation:500-533
See also: Requirements, Testing

Version Control
- Snapshot manager
- CLAUDE.md:50-52 (conventions)
- CLAUDE.md:49 (branch naming)
See also: Git, Workflow

Voice
- CLAUDE.md:60-66 (requirements)
- cake/components/voice_similarity_gate.py
  - reference corpus:133-143
  - ≥90% similarity required
See also: Operator, Messages

VoiceSimilarityGate
- cake/components/voice_similarity_gate.py
  - TF-IDF vectorization:86-101
  - message validation:194-226
  - corpus management:145-187
See also: Voice, Validation

## W

Watchdog
- cake/core/watchdog.py
- <100ms latency requirement
See also: Monitoring, Detection

Workflow
- CLAUDE.md:20-44 (development)
- CLAUDE.md:46-54 (git)
See also: Process, Methodology

## Y

YAML
- cake_config.yaml
See also: Configuration, Serialization

## Z

Zero-Escalation
- CLAUDE.md:13
See also: Autonomy, Architecture