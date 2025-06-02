# CAK → CAKE Component Mapping

## Core CAKE Components (from spec)
1. **CakeController** ← `text 6.txt` (cak_controller.py)
2. **Operator** ← `text 18.txt`, `text 25.txt` (operator.py) - DUPLICATES
3. **RecallDB** ← `text 19.txt`, `text 24.txt` (recall_db.py) - DUPLICATES  
4. **PTYShim** ← `text 29.txt` (pty_shim.py)
5. **Validator** ← `text 7.txt` (task_convergence_validator.py)
6. **Watchdog** ← NOT FOUND - Need to implement
7. **SnapshotManager** ← `text 30.txt` (snapshot_manager.py)
8. **VoiceSimilarityGate** ← NOT FOUND - Need to implement
9. **KnowledgeLedger** ← `text 9.txt` (cross_task_knowledge_ledger.py)

## Additional Components Found
- `text 2.txt` - stage_router.py (TRRDEVS router)
- `text 3.txt` - rule_creator.py 
- `text 4.txt` - info_fetcher.py
- `text 8.txt` - adaptive_confidence_system.py
- `text 10.txt` - semantic_error_classifier.py (enhanced validator)
- `text 11.txt` - claude_prompt_orchestration.py
- `text 13.txt` - models.py (data models)
- `text 14.txt` - rate_limiter.py
- `text 15.txt` - test_cak_core.py (tests!)
- `text 20.txt` - cak_adapter.py
- `text 22.txt`, `text 27.txt` - cak_integration.py - DUPLICATES

## Missing Components (need to implement)
- Watchdog (stream monitor)
- VoiceSimilarityGate (style checker)

## Next Steps
1. Rename all CAK → CAKE
2. Place files in proper directories:
   - `/cake/core/` - CakeController, stage_router
   - `/cake/components/` - Operator, Validator, RecallDB, etc.
   - `/cake/utils/` - models, rate_limiter, etc.
3. Resolve duplicates (pick best version)
4. Implement missing components