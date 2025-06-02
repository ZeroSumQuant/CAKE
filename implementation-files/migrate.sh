#!/bin/bash
# Migration script: CAK → CAKE

echo "🎂 Starting CAK → CAKE Migration..."
echo "=================================="

# Create CAKE directory structure
echo "📁 Creating directory structure..."
mkdir -p ../cake/core
mkdir -p ../cake/components  
mkdir -p ../cake/utils
mkdir -p ../cake/adapters
mkdir -p ../tests/unit
mkdir -p ../tests/integration

# Function to migrate a file
migrate_file() {
    local src_file=$1
    local dest_dir=$2
    local new_name=$3
    
    echo "  → Migrating $src_file to $dest_dir/$new_name"
    
    # Copy file and replace CAK with CAKE
    sed 's/CAK/CAKE/g; s/cak/cake/g' "$src_file" > "$dest_dir/$new_name"
}

echo ""
echo "🔄 Migrating Core Components..."
migrate_file "text 6.txt" "../cake/core" "cake_controller.py"
migrate_file "text 2.txt" "../cake/core" "stage_router.py"

echo ""
echo "🔧 Migrating Components..."
migrate_file "text 25.txt" "../cake/components" "operator.py"  # Using newer version
migrate_file "text 24.txt" "../cake/components" "recall_db.py"  # Using newer version
migrate_file "text 29.txt" "../cake/components" "pty_shim.py"
migrate_file "text 7.txt" "../cake/components" "validator.py"
migrate_file "text 30.txt" "../cake/components" "snapshot_manager.py"
migrate_file "text 9.txt" "../cake/components" "knowledge_ledger.py"
migrate_file "text 10.txt" "../cake/components" "semantic_error_classifier.py"

echo ""
echo "🛠️ Migrating Utils..."
migrate_file "text 13.txt" "../cake/utils" "models.py"
migrate_file "text 14.txt" "../cake/utils" "rate_limiter.py"
migrate_file "text 8.txt" "../cake/utils" "adaptive_confidence.py"
migrate_file "text 3.txt" "../cake/utils" "rule_creator.py"
migrate_file "text 4.txt" "../cake/utils" "info_fetcher.py"

echo ""
echo "🔌 Migrating Adapters..."
migrate_file "text 20.txt" "../cake/adapters" "cake_adapter.py"
migrate_file "text 27.txt" "../cake/adapters" "cake_integration.py"  # Using newer version
migrate_file "text 11.txt" "../cake/adapters" "claude_orchestration.py"

echo ""
echo "✅ Migrating Tests..."
migrate_file "text 15.txt" "../tests/unit" "test_cake_core.py"

echo ""
echo "📊 Migration Summary:"
echo "  - Core: 2 files"
echo "  - Components: 7 files"
echo "  - Utils: 5 files"
echo "  - Adapters: 3 files"
echo "  - Tests: 1 file"
echo "  - Total: 18 files migrated"

echo ""
echo "⚠️  Missing Components (need to implement):"
echo "  - Watchdog (stream monitor)"
echo "  - VoiceSimilarityGate (style consistency checker)"

echo ""
echo "✨ Migration complete! Next steps:"
echo "  1. Create __init__.py files"
echo "  2. Fix imports between modules"
echo "  3. Implement missing components"
echo "  4. Run tests"