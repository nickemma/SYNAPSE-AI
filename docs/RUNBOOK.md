# RUNBOOK — SYNAPSE-AI

**Purpose:** Procedures for operating and recovering SYNAPSE-AI in production.

**Last Updated:** June 24, 2026  
**On-Call:** Check Slack #on-call-rotation  
**Escalation:** tech-leads@synapse-ai.internal

---

## Table of Contents

1. [Startup & Initialization](#startup--initialization)
2. [Common Operations](#common-operations)
3. [Failure Scenarios & Recovery](#failure-scenarios--recovery)
4. [Key Rotation & Maintenance](#key-rotation--maintenance)
5. [Disaster Recovery](#disaster-recovery)
6. [Monitoring & Alerting](#monitoring--alerting)

---

## Startup & Initialization

### Cold Start (First Boot)

**Prerequisites:**
- [ ] Kubernetes cluster running (3+ nodes)
- [ ] PostgreSQL database accessible
- [ ] AWS KMS accessible (for encryption keys)
- [ ] S3 bucket for backups accessible

**Procedure:**

1. **Initialize the consent ledger:**
   ```bash
   ./bin/synapse-admin init-ledger \
     --ledger-path /var/lib/synapse/ledger \
     --kms-key-id arn:aws:kms:...
   ```
   Expected output: `Ledger initialized with root hash: sha256:...`

2. **Start the storage service:**
   ```bash
   docker-compose up synapse-storage
   ```
   Wait for: `[INFO] Storage service listening on :9090`

3. **Start the gateway:**
   ```bash
   docker-compose up synapse-gateway
   ```
   Wait for: `[INFO] Gateway listening on :8443 (mTLS)`

4. **Verify connectivity:**
   ```bash
   ./bin/synapse-cli health \
     --gateway localhost:8443 \
     --ca-cert /etc/synapse/ca.pem \
     --client-cert /etc/synapse/client.pem
   ```
   Expected: `Status: healthy. Storage: OK. Ledger: OK.`

5. **Start the inference service:**
   ```bash
   docker-compose up synapse-inference
   ```

6. **Start the federated orchestrator:**
   ```bash
   docker-compose up synapse-fl-orchestrator
   ```

**Verification:**
- Run end-to-end test:
  ```bash
  ./scripts/e2e-test.sh
  ```
  Should complete in <30 seconds

---

### Warm Start (Restart After Outage)

1. **Check ledger integrity on startup:**
   ```bash
   # This happens automatically on boot; monitor logs
   docker-compose logs synapse-gateway | grep "ledger integrity"
   ```
   If you see `FAIL`, goto → **Failure Scenario: Ledger Corruption**

2. **Verify backup was recent:**
   ```bash
   aws s3 ls s3://synapse-backups/latest/ --human-readable
   ```
   Should show a backup from <24 hours ago

3. **Bring services up in order:**
   ```bash
   docker-compose up -d synapse-storage
   sleep 10
   docker-compose up -d synapse-gateway
   sleep 10
   docker-compose up -d synapse-inference synapse-fl-orchestrator
   ```

4. **Monitor the startup sequence:**
   ```bash
   watch -n 2 'docker-compose logs --tail 20'
   ```

---

## Common Operations

### Adding a New Subject (Enrollment)

**Prerequisites:** Subject has downloaded the edge app and provided personal information

**Procedure:**

1. **Generate enrollment token:**
   ```bash
   ./bin/synapse-admin subject create \
     --subject-name "Jane Doe" \
     --email jane@example.com \
     --phone +234-xxx-xxxx
   ```
   Output: `enrollment_token: provisioning-abc123def456` + expiry (24 hours)

2. **Subject enters token in app:**
   - Subject opens edge app
   - Selects "Enroll"
   - Enters token
   - App generates device cert request

3. **Verify enrollment in logs:**
   ```bash
   docker-compose logs synapse-gateway | grep "subject.*enrolled"
   ```

4. **Verify key material was generated:**
   ```bash
   aws kms describe-key --key-id $(aws kms list-keys | jq -r '.Keys[0].KeyId')
   ```

---

### Granting Consent for a Model

**Prerequisites:** Subject is enrolled; model is deployed

**Procedure:**

1. **Subject initiates grant via web UI:**
   - Subject logs in
   - Selects "Grant Consent"
   - Chooses model: "mental-state-classifier@v2.3"
   - Chooses purpose: "attention/fatigue research"
   - Sets TTL: "30 days"
   - Confirms with 2FA (email/SMS)

2. **Verify grant was created:**
   ```bash
   ./bin/synapse-cli consent list --subject <subject-id>
   ```
   Should show a grant with status `ACTIVE`

3. **Test that inference is allowed:**
   ```bash
   ./bin/synapse-cli infer \
     --subject <subject-id> \
     --model mental-state-classifier@v2.3 \
     --requester test-lab
   ```
   Should return a prediction + provenance record

---

### Revoking Consent

**Prerequisites:** Subject has an active grant

**Procedure:**

1. **Subject revokes via web UI or CLI:**
   ```bash
   ./bin/synapse-cli consent revoke \
     --subject <subject-id> \
     --grant-id <grant-id>
   ```
   Output: `Revocation recorded. Status: active → revoked.`

2. **Verify revocation was recorded:**
   ```bash
   ./bin/synapse-cli consent list --subject <subject-id> --verbose
   ```
   Should show a revocation record with timestamp

3. **Verify inference is now denied:**
   ```bash
   ./bin/synapse-cli infer \
     --subject <subject-id> \
     --model mental-state-classifier@v2.3
   ```
   Should fail with `consent_status: REVOKED`

**Timing:** Revocation should be honored within 60 seconds (cache TTL)

---

### Initiating a Federated Learning Round

**Prerequisites:** At least 3 nodes are available and have opt-in for training

**Procedure:**

1. **Check node availability:**
   ```bash
   ./bin/synapse-fl status --nodes
   ```
   Output should show ≥3 nodes in `ready` state

2. **Start a round:**
   ```bash
   ./bin/synapse-fl round start \
     --model mental-state-classifier \
     --training-epochs 5 \
     --dp-epsilon 2.0 \
     --min-nodes 3
   ```
   Output: `Round ID: round-20260624-001`

3. **Monitor progress:**
   ```bash
   watch -n 5 './bin/synapse-fl round status --round-id round-20260624-001'
   ```
   Status should progress: `initializing` → `training` → `aggregating` → `complete`

4. **Verify aggregated model:**
   ```bash
   ./bin/synapse-model info --model mental-state-classifier --version latest
   ```
   Should show the new version with training metadata

---

## Failure Scenarios & Recovery

### Scenario 1: Consent Service is Down

**Symptoms:**
- Inference requests fail with `consent service unavailable`
- Logs show connection timeouts to consent ledger
- PagerDuty alert: `consent-service-down`

**Diagnosis:**
```bash
# Check if service is running
docker-compose ps synapse-gateway
# Should show "up"

# Check logs for errors
docker-compose logs synapse-gateway --tail 50 | grep ERROR

# Check network connectivity to ledger
curl -k --cacert /etc/synapse/ca.pem \
  https://synapse-storage:9090/health
```

**Recovery (Option 1: Restart):**
```bash
docker-compose restart synapse-gateway
# Wait for service to come up
sleep 10
docker-compose logs synapse-gateway | grep "listening"
```

**Recovery (Option 2: Failover to Read Replica):**
```bash
# If you have a read replica
kubectl patch deployment synapse-gateway \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"gateway","env":[{"name":"CONSENT_LEDGER_HOST","value":"synapse-storage-replica.default"}]}]}}}}'
```

**Recovery (Option 3: Degraded Mode):**
If the service cannot recover, inference requests can be served with cached consent decisions (up to 60 seconds old):
```bash
SYNAPSE_CONSENT_CACHE_MODE=degraded \
docker-compose up -d synapse-gateway
```
⚠️ **Warning:** In degraded mode, revocations may be delayed by up to 60 seconds. Document this outage.

**Prevention:**
- Read replica of consent ledger (async updates, ~1 second lag)
- Circuit breaker: if consent service is slow (>500ms), switch to cached mode
- Monitoring: alert if consent-service latency exceeds 100ms

---

### Scenario 2: Storage Service is Down

**Symptoms:**
- Ingestion fails: `unable to write samples`
- Inference fails: `unable to read subject data`
- PagerDuty alert: `storage-service-down`

**Diagnosis:**
```bash
docker-compose ps synapse-storage
docker-compose logs synapse-storage --tail 50
```

**Recovery:**

1. **Check disk space:**
   ```bash
   df -h /var/lib/synapse
   # If >90% full, cleanup old logs
   ./scripts/cleanup-old-logs.sh --before 30-days-ago
   ```

2. **Check WAL integrity:**
   ```bash
   ./bin/synapse-admin storage-check \
     --path /var/lib/synapse/subjects
   ```
   If you see `corrupted WAL`, goto → **Scenario 4: WAL Corruption**

3. **Restart the service:**
   ```bash
   docker-compose restart synapse-storage
   sleep 5
   docker-compose logs synapse-storage | grep "ready"
   ```

4. **Verify it's accepting connections:**
   ```bash
   curl -k --cacert /etc/synapse/ca.pem \
     https://synapse-storage:9090/health
   ```

**Prevention:**
- Monitor disk usage; alert at 70%, 85%, 95%
- Replicate storage to S3 (incremental daily backup)
- Use a larger storage volume (or auto-scaling persistent volumes on K8s)

---

### Scenario 3: Ledger Hash Chain Broken

**Symptoms:**
- Startup fails with `ledger integrity check failed`
- Logs show: `[ERROR] Ledger hash mismatch at entry 12345: expected sha256:... got sha256:...`
- System is in read-only mode

**Diagnosis:**
```bash
# Identify which entry broke the chain
docker-compose logs synapse-gateway | grep "hash mismatch"
# Output: "at entry 12345"

# Examine the ledger around that entry
./bin/synapse-admin ledger inspect \
  --entry-range 12340-12350 \
  --verbose
```

**Recovery (Option 1: Truncate to Last Valid Entry):**
```bash
./bin/synapse-admin ledger truncate \
  --to-entry 12344 \
  --backup-path /tmp/ledger-truncated-backup
```
⚠️ **Warning:** This loses entries 12345+. Any grants/revocations made after that point are lost. Document the incident.

**Recovery (Option 2: Restore from Backup):**
```bash
# List available backups
aws s3 ls s3://synapse-backups/ledger/ --recursive | tail -20

# Restore latest
aws s3 cp s3://synapse-backups/ledger/latest/ledger.backup /tmp/
./bin/synapse-admin ledger restore --from /tmp/ledger.backup

# Verify integrity
./bin/synapse-admin ledger-check --path /var/lib/synapse/ledger
```

**Investigation:**
- Check if disk was full (no space to write, partial writes)
- Check if there was an unclean shutdown (power loss, OOM kill)
- Check logs for write errors in the period just before the mismatch

**Prevention:**
- Weekly ledger integrity verification (cron job):
  ```bash
  # In crontab
  0 2 * * 0 /opt/synapse/scripts/weekly-ledger-check.sh
  ```
- Ledger replication (Postgres WAL replication if using Postgres backend)

---

### Scenario 4: WAL Corruption (Neural Data Log)

**Symptoms:**
- Inference returns `[ERROR] Subject data corrupted`
- Logs show: `[ERROR] GCM authentication tag verification failed`
- A subject's historical data is unreadable

**Diagnosis:**
```bash
# Run WAL checker on the subject's data
./bin/synapse-admin storage-check \
  --subject <subject-id> \
  --verbose
# Output: "Sample 42: auth tag mismatch"

# Identify the corruption boundary
./bin/synapse-admin storage-check \
  --subject <subject-id> \
  --find-corruption-boundary
# Output: "Last valid sample: 41. First corrupted: 42."
```

**Recovery:**

1. **Truncate to last valid sample:**
   ```bash
   ./bin/synapse-admin storage-truncate \
     --subject <subject-id> \
     --to-sample 41 \
     --backup /tmp/wal-truncated
   ```

2. **Notify the subject:**
   - Email: "We detected data corruption in your neural signal history. Samples after [timestamp] are unavailable. No data loss; the remaining samples are intact."

3. **Reingest data if possible:**
   - Check if the subject has device backups (edge device stores samples locally)
   - Ask subject to sync device data again

**Prevention:**
- Crash-safe storage: fsync before ACK (already in place)
- Checksums: every sample has a GCM auth tag that catches corruption
- Monitoring: alert if any subject experiences auth tag failures

---

### Scenario 5: Privacy Budget Exhausted (Subject Locked Out)

**Symptoms:**
- Subject tries to infer; gets `[ERROR] epsilon_remaining <= 0`
- Subject can't request new inferences
- Logs show: `consent_status: active, privacy_budget: exhausted`

**Diagnosis:**
```bash
./bin/synapse-cli privacy-budget show --subject <subject-id>
# Output:
# epsilon_total: 1.0
# epsilon_spent: 1.0
# epsilon_remaining: 0.0
# reset_at: 2026-07-24T00:00:00Z
```

**Recovery (Expected / Intended):**
This is not a failure; it's a feature. The subject has spent their monthly privacy budget. Options:

1. **Subject waits for budget reset** (monthly, on the 1st)
2. **Subject requests manual reset** (for critical use cases):
   ```bash
   ./bin/synapse-cli privacy-budget request-reset \
     --subject <subject-id> \
     --reason "Important health decision"
   ```
   A manager must approve (via UI)

3. **Separate budgets by purpose** (configure different budget pools):
   - "attention research" ← epsilon_total: 0.5
   - "fatigue monitoring" ← epsilon_total: 0.5
   - Subject can switch pools

**Prevention:**
- Alert subject at ε=0.7, ε=0.9, ε=0.95
- Show burn rate: "You've spent 0.3ε in 10 days; budget exhaustion in ~23 days"
- UI dashboard: visualize remaining budget with a progress bar

---

### Scenario 6: Node Fails During Federated Round

**Symptoms:**
- Federated round hangs: `waiting for node-03 gradients (timeout in 45 seconds)`
- PagerDuty alert: `fl-round-stalled`

**Diagnosis:**
```bash
./bin/synapse-fl round status --round-id <round-id>
# Output:
# Status: training
# Nodes: node-01 (complete), node-02 (complete), node-03 (timed out)
# Elapsed: 1800s / 3600s timeout
```

**Recovery (Automatic):**
If ≥3 nodes are in the round, the system automatically tolerates 1 failure:
```bash
# The round continues
./bin/synapse-fl round wait --round-id <round-id>
# Output: "Aggregating gradients from 2 nodes. Status: aggregating"
# (and completes normally)
```

**Recovery (Manual, if <3 Nodes Remain):**
```bash
# Abort the round
./bin/synapse-fl round abort --round-id <round-id>

# Wait for the failed node to recover
watch -n 5 './bin/synapse-fl node-status --node node-03'

# Restart the round when the node is ready
./bin/synapse-fl round start --model mental-state-classifier --retry-round <round-id>
```

**Investigation:**
- Check the failed node's logs: `docker logs <node-03> --tail 100`
- Common causes: OOM, disk full, network partition
- If persistent, remove the node from the pool temporarily

**Prevention:**
- Node health checks: every 60 seconds, verify node is responsive
- Liveness probes: kill nodes that hang (K8s handles restart)
- Minimum node pool size: maintain 5+ nodes so losing 2 is acceptable

---

### Scenario 7: Model Inference Returns Suspicious Results

**Symptoms:**
- Inference output is nonsensical: `attention=NaN` or `attention=1.2` (outside [0, 1])
- Logs show: `[WARN] Model output is out of range`

**Diagnosis:**
```bash
./bin/synapse-admin model verify \
  --model mental-state-classifier@v2.3 \
  --test-data /tmp/test-eeg.csv
# Outputs model accuracy, consistency checks, numerical stability
```

**Recovery:**

1. **If the model file is corrupted:**
   ```bash
   # Rollback to previous version
   kubectl set image deployment/synapse-inference \
     inference=synapse-inference:v2.2
   # Monitor for improvement
   watch -n 5 'kubectl logs -l app=synapse-inference --tail 10'
   ```

2. **If the model is fine but data is bad:**
   - Check if subject's EEG has artifacts (poor electrode contact, electromagnetic interference)
   - Advise subject: "Ensure headset is properly fitted"

3. **If input pipeline is broken:**
   ```bash
   # Verify preprocessing
   ./bin/synapse-admin preprocess test \
     --input /tmp/sample-eeg.csv \
     --model mental-state-classifier@v2.3
   # Should output preprocessed features
   ```

**Prevention:**
- Model validation on deployment: verify on held-out test set before deploying
- Input validation: check that EEG samples are within expected range (e.g., ±500 µV)
- Output validation: check that prediction is in [0, 1] after softmax

---

## Key Rotation & Maintenance

### Monthly: Rotate Subject Data Keys

**Purpose:** Limit the impact of a key compromise to a single month's data.

**Procedure:**

1. **Schedule key rotations during low-traffic window:**
   ```bash
   # Monday, 2am UTC (low-traffic window for global users)
   0 2 * * 1 /opt/synapse/scripts/monthly-key-rotation.sh
   ```

2. **Key rotation script (automated):**
   ```bash
   for subject_id in $(./bin/synapse-admin list-subjects); do
     # Generate new key
     NEW_KEY=$(openssl rand -hex 32)
     
     # Store new key in KMS
     aws kms encrypt \
       --key-id <subject-id> \
       --plaintext $NEW_KEY \
       --output text --query CiphertextBlob > /tmp/new-key
     
     # Append to subject's key history
     ./bin/synapse-admin subject update-key \
       --subject-id $subject_id \
       --new-key /tmp/new-key
   done
   ```

3. **Verification:**
   ```bash
   # No re-encryption of old data; new samples use new key
   # Verify by checking metadata:
   ./bin/synapse-admin subject show-keys --subject <subject-id>
   # Should show current key + historical keys
   ```

---

### Quarterly: Ledger Root Hash Publication

**Purpose:** Create external evidence of the ledger state (for auditability).

**Procedure:**

1. **Compute current ledger root hash:**
   ```bash
   ./bin/synapse-admin ledger root-hash
   # Output: sha256:abcd1234...
   ```

2. **Publish to an external immutable log:**
   ```bash
   # Option A: Publish to a Merkle tree (e.g., via a trusted third party)
   curl -X POST https://auditor-service.external/publish \
     -H "Content-Type: application/json" \
     -d '{
       "timestamp": "2026-06-24T00:00:00Z",
       "ledger_root_hash": "sha256:abcd1234...",
       "num_entries": 123456,
       "signature": "..."
     }'
   
   # Option B: Publish to a blockchain (e.g., Ethereum mainnet)
   # (Post-MVP; not in current roadmap)
   ```

3. **Archive the publication:**
   ```bash
   aws s3 cp /tmp/ledger-publication-2026-Q2.json \
     s3://synapse-backups/ledger-publications/
   ```

---

### Bi-Annual: Full Disaster Recovery Drill

**Purpose:** Verify that recovery procedures actually work.

**Procedure:**

1. **Backup current state:**
   ```bash
   docker-compose exec synapse-storage \
     pg_dump synapse_db > /tmp/backup-$(date +%s).sql
   ```

2. **Simulate total data loss:**
   ```bash
   # ⚠️ Do this in a staging environment, not production!
   rm -rf /var/lib/synapse/subjects/*
   ```

3. **Restore from backup:**
   ```bash
   docker-compose exec synapse-storage \
     psql synapse_db < /tmp/backup-*.sql
   ```

4. **Verify everything is functional:**
   ```bash
   ./scripts/e2e-test.sh --subject <test-subject> --verbose
   # Should pass all tests
   ```

5. **Document findings:**
   - How long did recovery take?
   - Were any data inconsistencies found?
   - Update runbook with any lessons learned

---

## Monitoring & Alerting

### Key Metrics (Prometheus)

```yaml
# Ingestion
synapse_samples_ingested_total           # counter: total EEG samples
synapse_ingestion_latency_ms             # histogram: ingestion latency
synapse_ingestion_errors_total           # counter: rejected samples

# Consent
synapse_consent_checks_total             # counter: consent verifications
synapse_consent_granted_total            # counter: grants issued
synapse_consent_revoked_total            # counter: revocations
synapse_consent_check_latency_ms         # histogram: lookup latency

# Inference
synapse_inferences_total                 # counter: inferences served
synapse_inference_denials_total          # counter: denied due to consent/budget
synapse_inference_latency_ms             # histogram: end-to-end latency
synapse_inference_budget_exhausted_total # counter: budget exhaustion

# Privacy
synapse_epsilon_spent_per_subject        # gauge: ε spent per subject
synapse_epsilon_remaining_per_subject    # gauge: ε remaining per subject

# Federated Learning
synapse_fl_round_duration_s              # histogram: round duration
synapse_fl_nodes_in_round                # gauge: num nodes
synapse_fl_round_failures_total          # counter: aborted rounds

# Storage
synapse_wal_size_bytes                   # gauge: WAL file size
synapse_disk_used_percent                # gauge: % disk usage
synapse_storage_latency_ms               # histogram: read/write latency

# Ledger
synapse_ledger_entries_total             # counter: total ledger entries
synapse_ledger_hash_chain_failures_total # counter: integrity failures
```

### Critical Alerts

| Alert | Threshold | Action |
| --- | --- | --- |
| `consent-service-down` | Service unreachable for 1 min | Page on-call; verify mTLS certs |
| `storage-service-down` | Service unreachable for 1 min | Page on-call; check disk space |
| `ledger-integrity-failure` | Any | Page immediately; follow Scenario 3 |
| `wal-corruption` | Any | Page immediately; follow Scenario 4 |
| `disk-usage-critical` | >90% | Page on-call; archive old logs |
| `fl-round-stalled` | >2 hours in `training` | Check node status; follow Scenario 6 |
| `inference-latency-p99` | >500ms | Investigate consent cache; check storage |
| `consent-check-cache-hitrate` | <80% | Increase TTL or add caching layer |

---

## Communication During Incidents

### Incident Severity Levels

**Severity 1 (Critical):**
- Subject data is exposed or lost
- Ledger is corrupted
- System is completely down

**Response:**
1. Page the entire team (Slack + phone)
2. Open incident bridge: Zoom + Slack thread
3. CTO takes incident commander role
4. Update status page every 15 minutes

**Severity 2 (Major):**
- A service is down but others are operational
- A node is failed but round continues
- Consent service is slow (>100ms)

**Response:**
1. Page on-call engineer
2. Update #incidents Slack channel
3. Resolve within 2 hours or escalate to Severity 1

**Severity 3 (Minor):**
- A metric is out of bounds
- A non-critical service is slow
- An anomaly detector triggered

**Response:**
1. Log in #alerts Slack channel
2. Investigate during next scheduled maintenance window

---

## Useful Commands

```bash
# Health check
./bin/synapse-cli health

# Subject status
./bin/synapse-cli subject show <subject-id>

# Consent list
./bin/synapse-cli consent list --subject <subject-id>

# Privacy budget
./bin/synapse-cli privacy-budget show --subject <subject-id>

# Recent inferences
./bin/synapse-cli audit recent-inferences --subject <subject-id> --limit 10

# Storage stats
./bin/synapse-admin storage-stats

# Ledger status
./bin/synapse-admin ledger-status

# Model info
./bin/synapse-model info --model <model-name> --version <version>
```

---

## Escalation Path

**Level 1 (On-Call):** Debug and attempt recovery  
**Level 2 (Tech Lead):** Escalate if >30 min to resolution  
**Level 3 (CTO):** Escalate if customer impact + high severity  
**Level 4 (CEO):** Escalate if regulatory/legal exposure  

---

**Last reviewed:** [Date]  
**Next review:** [Date + 6 months]  
**Owner:** Platform Engineering
