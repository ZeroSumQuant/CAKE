# CAKE Deployment & Operations Guide

**This is the authoritative deployment and operations contract for CAKE.**

## Quick Start (REQUIRED steps)

### Prerequisites Check
```bash
# MUST have these installed
python --version  # Requires 3.8+
poetry --version  # Or pip 20.0+
git --version     # 2.0+
sqlite3 --version # 3.32+ (for WAL support)
```

### Installation Commands (MUST run in order)
```bash
# 1. Clone repository
git clone https://github.com/your-org/cake.git
cd cake

# 2. Install dependencies
poetry install  # OR: pip install -r requirements.txt

# 3. Initialize database
poetry run alembic upgrade head

# 4. Create default config
poetry run cake init --output=cake_config.yaml

# 5. Run self-test
poetry run cake self-test

# 6. Start CAKE
poetry run cake start --adapter=claude-code
```

### Expected Output for Each Step
```bash
# Step 3 expected output:
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Add indexes
Database initialized successfully

# Step 5 expected output:
Running CAKE self-test...
✓ Database connection OK
✓ Configuration valid
✓ All components loadable
✓ Adapter connection OK
✓ Metrics endpoint responding
Self-test PASSED

# Step 6 expected output:
CAKE Status: RUNNING
Adapter: claude-code (healthy)
Monitoring streams: stdout, stderr
Metrics: http://localhost:9090/metrics
```

### Configuration File (MUST exist before start)
```yaml
# cake_config.yaml (REQUIRED fields)
version: "1.0"
strictness: balanced
escalation:
  max_strikes: 4
  cooldown_minutes: 5
```

## Post-Deploy Health Check

### Health Check Script (REQUIRED after deployment)
```bash
#!/bin/bash
# scripts/post_deploy_health_check.sh

echo "Running post-deployment health check..."

# 1. Check process running
if ! pgrep -f "cake start" > /dev/null; then
    echo "FAIL: CAKE process not running"
    exit 1
fi

# 2. Check health endpoint
HEALTH=$(curl -s http://localhost:8080/health)
if [[ $HEALTH != *"healthy"* ]]; then
    echo "FAIL: Health endpoint not responding correctly"
    echo "Response: $HEALTH"
    exit 1
fi

# 3. Check metrics endpoint
METRICS=$(curl -s http://localhost:9090/metrics | grep cake_)
if [[ -z "$METRICS" ]]; then
    echo "FAIL: Metrics not being exported"
    exit 1
fi

# 4. Test intervention system
echo "import nonexistent_module" | poetry run cake test-intervention
if [[ $? -ne 0 ]]; then
    echo "FAIL: Intervention system not working"
    exit 1
fi

echo "✓ Process running"
echo "✓ Health endpoint OK"
echo "✓ Metrics exported"
echo "✓ Intervention system OK"
echo "Health check PASSED"
```

**Good Output**:
```
Running post-deployment health check...
✓ Process running
✓ Health endpoint OK
✓ Metrics exported
✓ Intervention system OK
Health check PASSED
```

**Bad Output Examples**:
```
FAIL: CAKE process not running
# Action: Run `poetry run cake start`

FAIL: Health endpoint not responding correctly
Response: {"status": "unhealthy", "error": "database locked"}
# Action: Check database permissions, restart CAKE
```

## Deployment Modes

### 1. Local Development (Default Path)
```bash
# Start with verbose logging (MANUAL STEP)
poetry run cake start \
  --config=cake_config.yaml \
  --adapter=claude-code \
  --log-level=DEBUG \
  --metrics-port=9090

# Verify running (MANUAL STEP)
poetry run cake status
```

**Expected Status Output**:
```json
{
  "status": "RUNNING",
  "adapter": "claude-code",
  "adapter_health": "healthy",
  "uptime_seconds": 323,
  "total_interventions": 0,
  "components": {
    "controller": "running",
    "watchdog": "monitoring",
    "validator": "ready",
    "recall_db": "connected",
    "operator": "ready"
  }
}
```

### 2. Docker Deployment
```yaml
# docker-compose.yml (REQUIRED)
version: '3.8'
services:
  cake:
    image: cake:latest
    volumes:
      - ./cake_config.yaml:/app/cake_config.yaml:ro
      - cake-data:/app/data
      - cake-logs:/app/logs
    ports:
      - "9090:9090"  # Metrics
      - "8080:8080"  # Health API
    environment:
      - CAKE_ENV=production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "cake", "health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  cake-data:
  cake-logs:
```

**Deploy Commands** (MANUAL STEPS):
```bash
# Build image
docker build -t cake:latest .

# Start services
docker-compose up -d

# View logs
docker-compose logs -f cake

# Stop services
docker-compose down
```

### 3. Kubernetes Deployment
```yaml
# k8s/cake-deployment.yaml (REQUIRED)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cake-controller
spec:
  replicas: 1  # Single instance for v1
  selector:
    matchLabels:
      app: cake
  template:
    metadata:
      labels:
        app: cake
    spec:
      containers:
      - name: cake
        image: cake:latest
        ports:
        - containerPort: 9090
          name: metrics
        - containerPort: 8080
          name: health
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /app/cake_config.yaml
          subPath: cake_config.yaml
        - name: data
          mountPath: /app/data
      volumes:
      - name: config
        configMap:
          name: cake-config
      - name: data
        persistentVolumeClaim:
          claimName: cake-data-pvc
```

**Deploy Commands** (MANUAL STEPS):
```bash
# Create namespace
kubectl create namespace cake

# Create config
kubectl create configmap cake-config \
  --from-file=cake_config.yaml \
  -n cake

# Deploy
kubectl apply -f k8s/ -n cake

# Check status
kubectl get pods -n cake
kubectl logs -f deployment/cake-controller -n cake
```

## Database Management

### Initialize Database (REQUIRED on first run)
```bash
# Create schema (AUTOMATED via CI)
poetry run alembic upgrade head

# Verify tables (MANUAL verification)
poetry run cake db verify
```

**Expected Verification Output**:
```
Checking database structure...
✓ error_memory table exists (14 columns)
✓ pattern_violations table exists (5 columns)
✓ Indexes created (idx_signature, idx_expires)
✓ WAL mode enabled
✓ Connection pool configured (max=5)
Database verification PASSED
```

### Backup Procedures (MUST run daily via cron)
```bash
# Full backup (AUTOMATED via cron)
poetry run cake backup \
  --output=/backups/cake-$(date +%Y%m%d-%H%M%S).tar.gz \
  --include-db \
  --include-logs \
  --include-snapshots

# Database only (AUTOMATED via cron)
poetry run cake db export \
  --format=sql \
  --output=/backups/cake-db-$(date +%Y%m%d).sql

# Verify backup (MANUAL verification)
poetry run cake backup verify \
  --file=/backups/cake-20240115-120000.tar.gz
```

**Expected Backup Verification Output**:
```json
{
  "backup_valid": true,
  "components": {
    "database": "OK (2.3MB)",
    "logs": "OK (45.2MB)", 
    "snapshots": "OK (123.4MB)",
    "config": "OK (1.2KB)"
  },
  "total_size": "171.1MB",
  "created": "2024-01-15T12:00:00Z"
}
```

### Restore Procedures
```bash
# Full restore (MANUAL STEP - requires confirmation)
poetry run cake restore \
  --input=/backups/cake-20240115-120000.tar.gz \
  --confirm

# Database only (MANUAL STEP)
poetry run cake db import \
  --input=/backups/cake-db-20240115.sql \
  --confirm

# Selective restore (MANUAL STEP)
poetry run cake restore \
  --input=/backups/cake-20240115-120000.tar.gz \
  --only=database \
  --confirm
```

**Expected Restore End State**:
- System returns to exact state at backup time
- All error history preserved
- Configuration matches backup
- No data loss between backup and restore

### Database Maintenance (MUST run weekly via cron)
```bash
# Clean expired entries (AUTOMATED via cron)
poetry run cake db cleanup \
  --older-than=24h

# Optimize database (AUTOMATED via cron)
poetry run cake db optimize

# Check integrity (MANUAL verification)
poetry run cake db check
```

**Expected Maintenance Output**:
```
Database cleanup:
  Expired entries removed: 1,247
  Space reclaimed: 12.3MB
  
Database optimization:
  VACUUM completed
  ANALYZE completed
  REINDEX completed
  
Database integrity check: PASSED
```

## Rollback Procedures

### Application Rollback
```bash
# List available versions (MANUAL STEP)
poetry run cake versions list
```

**Expected Version List**:
```
Available CAKE versions:
  1.2.0 (current) - installed 2024-01-15
  1.1.0 - installed 2024-01-10
  1.0.0 - installed 2024-01-01
```

```bash
# Rollback to previous (MANUAL STEP - requires confirmation)
poetry run cake rollback --version=1.1.0 --confirm

# Verify rollback (MANUAL verification)
poetry run cake version
```

**Expected After Rollback**:
```
CAKE version 1.1.0
Rollback completed successfully
All components restarted
```

### Snapshot Rollback (for code/state)
```bash
# List snapshots (MANUAL STEP)
poetry run cake snapshot list
```

**Expected Snapshot List**:
```
ID                                    Label              Created              Size
550e8400-e29b-41d4-a716-446655440000  pre-force-push    2024-01-15 10:30:00  45MB
660e8400-e29b-41d4-a716-446655440001  ci-green-state    2024-01-15 09:00:00  42MB
770e8400-e29b-41d4-a716-446655440002  before-refactor   2024-01-15 08:00:00  41MB
```

```bash
# Rollback to snapshot (MANUAL STEP - requires confirmation)
poetry run cake snapshot restore \
  --id=550e8400-e29b-41d4-a716-446655440000 \
  --confirm

# Verify restoration (MANUAL verification)
poetry run cake snapshot verify
```

**Expected After Snapshot Restore**:
```
Snapshot restoration complete:
  Git HEAD: abc123def (matches snapshot)
  Working directory: clean
  Stashed changes: 2 (preserved)
  Database state: restored
```

### If Rollback Fails
1. **Application rollback fails**: Reinstall from backup package
2. **Snapshot restore fails**: Use git reset --hard with stashed changes
3. **Database restore fails**: Restore from SQL backup
4. **Complete failure**: Follow disaster recovery procedure

## Health Monitoring

### Health Check Endpoints
```bash
# Basic health (AUTOMATED monitoring)
curl http://localhost:8080/health
```

**Expected Healthy Response**:
```json
{
  "status": "healthy",
  "version": "1.2.0",
  "uptime": 3600
}
```

**Expected Unhealthy Response**:
```json
{
  "status": "unhealthy",
  "version": "1.2.0",
  "errors": ["database_locked", "adapter_timeout"]
}
```

```bash
# Detailed health (MANUAL check)
curl http://localhost:8080/health/detailed
```

**Expected Detailed Response**:
```json
{
  "status": "healthy",
  "components": {
    "controller": "running",
    "database": "connected",
    "adapter": "healthy",
    "metrics": "serving"
  },
  "stats": {
    "uptime_seconds": 3600,
    "intervention_count": 42,
    "error_prevention_rate": 0.89,
    "db_connections": 3
  },
  "last_intervention": "2024-01-15T10:30:00Z"
}
```

```bash
# Readiness check (AUTOMATED via k8s/docker)
curl http://localhost:8080/ready
# Returns 200 if ready, 503 if not
```

### Metrics Endpoints
```bash
# Prometheus metrics (AUTOMATED scraping)
curl http://localhost:9090/metrics
```

**Key Metrics to Monitor**:
```
# Expected values for healthy system:
cake_interventions_total > 0 (after 1 hour)
cake_response_latency_seconds{p99} < 0.5
cake_errors_prevented_total > cake_interventions_total * 0.85
cake_db_connections_active <= 5
cake_voice_similarity_score > 0.9
```

### Log Monitoring
```bash
# Tail logs (MANUAL monitoring)
poetry run cake logs --follow

# Search logs (MANUAL investigation)
poetry run cake logs \
  --since="1h" \
  --level=ERROR \
  --component=operator

# Export logs (MANUAL export)
poetry run cake logs export \
  --since="2024-01-15" \
  --format=json \
  --output=logs-export.json
```

**Expected Log Patterns (Healthy)**:
```
INFO  [controller] State transition: MONITORING -> DETECTING
INFO  [validator] Classified error as ImportError (confidence: 0.95)
INFO  [operator] Generated intervention: "Operator (CAKE): Stop..."
INFO  [adapter] Intervention delivered successfully
```

**Expected Log Patterns (Issues)**:
```
ERROR [recall_db] Connection timeout after 3 retries
WARN  [controller] Switching to in-memory fallback
ERROR [adapter] Failed to inject intervention: session not found
```

## Configuration Management

### Update Configuration (without restart)
```bash
# Edit config file (MANUAL STEP)
vim cake_config.yaml

# Validate changes (MANUAL STEP)
poetry run cake config validate --file=cake_config.yaml

# Apply changes (AUTOMATED hot-reload)
poetry run cake config reload
```

**Expected Reload Output**:
```
Validating configuration...
✓ Version: 1.0
✓ Strictness: paranoid (was: balanced)
✓ Max strikes: 4
✓ Cooldown: 5 minutes
Configuration reloaded successfully
All components notified of changes
```

### Environment-Specific Overrides
```bash
# Development (MANUAL SET)
export CAKE_ENV=development
export CAKE_STRICTNESS=minimal
export CAKE_LOG_LEVEL=DEBUG

# Production (MANUAL SET)
export CAKE_ENV=production
export CAKE_STRICTNESS=paranoid
export CAKE_LOG_LEVEL=INFO
```

## Troubleshooting Procedures

### High Intervention Rate
```bash
# 1. Check intervention frequency (MANUAL)
poetry run cake metrics --name=cake_interventions_total --period=1h
```

**If rate > 2/minute**:
```bash
# 2. Analyze patterns (MANUAL)
poetry run cake analyze interventions --last=100

# 3. Adjust cooldown (MANUAL)
poetry run cake config set escalation.cooldown_minutes=10

# 4. Verify change (MANUAL)
poetry run cake config show --key=escalation.cooldown_minutes
```

### Database Lock Issues
```bash
# 1. Check active connections (MANUAL)
poetry run cake db connections
```

**Expected Output**:
```
Active connections: 3/5
  PID 1234: controller (idle 2s)
  PID 1235: recall_db (active - query)
  PID 1236: metrics (idle 45s)
```

**If connections >= 5**:
```bash
# 2. Kill stuck connections (MANUAL)
poetry run cake db kill-connections --idle-time=5m

# 3. Enable WAL if needed (MANUAL)
poetry run cake db enable-wal

# 4. Monitor locks (MANUAL)
poetry run cake db locks --watch
```

### Memory Growth
```bash
# 1. Check memory usage (MANUAL)
poetry run cake stats memory
```

**Expected Output**:
```json
{
  "total_mb": 487,
  "components": {
    "controller": 45,
    "recall_db": 123,
    "snapshots": 234,
    "other": 85
  },
  "growth_rate_mb_per_hour": 12
}
```

**If total > 800MB**:
```bash
# 2. Force garbage collection (MANUAL)
poetry run cake gc --aggressive

# 3. Clean old snapshots (MANUAL)
poetry run cake snapshot cleanup --older-than=72h

# 4. Restart if needed (MANUAL)
poetry run cake restart --graceful
```

## Emergency Procedures

### Force Stop (CAUTION - MANUAL ONLY)
```bash
# Graceful stop (30s timeout)
poetry run cake stop --graceful --timeout=30

# Force stop (immediate)
poetry run cake stop --force

# Kill all CAKE processes (LAST RESORT)
pkill -f "cake"
```

**Expected State After Stop**:
- All interventions completed
- Database connections closed
- Snapshots saved
- Logs flushed

### Disable All Interventions
```bash
# Temporary disable (MANUAL - 1 hour)
poetry run cake disable interventions --duration=1h

# Permanent disable (MANUAL - requires restart)
poetry run cake config set interventions.enabled=false
poetry run cake restart
```

**Confirmation Required**:
```
WARNING: This will disable all automatic interventions
Type 'DISABLE' to confirm: DISABLE
Interventions disabled for 1 hour
```

### Reset to Factory Defaults
```bash
# WARNING: Deletes all data (MANUAL - REQUIRES EXPLICIT CONFIRMATION)
poetry run cake reset --factory --confirm=RESET
```

**Expected Reset Process**:
```
Confirm factory reset by typing 'RESET': RESET
Backing up current state to /tmp/cake-backup-20240115.tar.gz
Stopping all components...
Deleting database...
Removing snapshots...
Clearing logs...
Factory reset complete

# Reinitialize (MANUAL)
poetry run cake init
poetry run alembic upgrade head
```

## Monitoring Setup

### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cake'
    static_configs:
      - targets: ['localhost:9090']
```

### Alert Rules (REQUIRED)
```yaml
# alerts.yml
groups:
  - name: cake_alerts
    rules:
      - alert: HighInterventionRate
        expr: rate(cake_interventions_total[5m]) > 2
        for: 5m
        annotations:
          summary: "High intervention rate detected"
          action: "Check for error loops, increase cooldown"
          
      - alert: PerformanceDegradation
        expr: cake_response_latency_seconds{quantile="0.99"} > 0.5
        for: 5m
        annotations:
          summary: "Performance degradation detected"
          action: "Check CPU/memory, restart if needed"
          
      - alert: DatabaseConnectionExhaustion
        expr: cake_db_connections_active >= 5
        for: 1m
        annotations:
          summary: "Database connection pool exhausted"
          action: "Kill idle connections, check for deadlocks"
```

### Grafana Dashboard Import
```bash
# Import provided dashboard (MANUAL)
curl -X POST http://admin:admin@localhost:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d @grafana/cake-dashboard.json
```

**Expected Dashboard Panels**:
- Intervention rate (line graph)
- Error types (pie chart)
- Response latency (histogram)
- System health (status panel)
- Recent interventions (table)

## Scaling Guidelines

### Vertical Scaling Thresholds
- CPU > 80% sustained → Add 2 cores
- Memory > 80% → Add 2GB RAM
- Disk I/O > 1000 IOPS → Switch to SSD
- Network > 100Mbps → Upgrade bandwidth

### Horizontal Scaling
**NOT SUPPORTED in v1.0**
- Single instance only
- No clustering support
- No load balancing

## Security Checklist

### Required Security Measures
- [x] Run as non-root user (MUST verify)
- [x] Set file permissions: `chmod 600 cake_config.yaml` (MANUAL)
- [x] Enable audit logging: `audit_all_commands: true` (CONFIG)
- [x] Rotate logs: Max 100MB per file (AUTOMATED)
- [x] Use HTTPS for webhooks (CONFIG)
- [x] Restrict metrics endpoint access (FIREWALL)
- [x] Regular security updates: `poetry update --dry-run` (WEEKLY)

### Audit Commands
```bash
# View audit log (MANUAL)
poetry run cake audit --last=100

# Export for compliance (MANUAL)
poetry run cake audit export \
  --format=csv \
  --since="2024-01-01" \
  --output=audit-q1-2024.csv

# Check permissions (MANUAL)
poetry run cake security check
```

**Expected Security Check Output**:
```
Security Check Results:
✓ Config file permissions: 600
✓ Database file permissions: 600
✓ Running as non-root user
✓ Audit logging enabled
✓ No world-writable directories
✓ Dependencies up to date
Security check PASSED
```