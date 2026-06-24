# DESIGN DOCUMENT — SYNAPSE-AI

**Last Updated:** June 24, 2026  
**Status:** Pre-Implementation  
**Audience:** Engineers, architects, security reviewers

---

## Table of Contents

1. [Consent Engine](#consent-engine)
2. [Storage Layer](#storage-layer)
3. [Differential Privacy Budget](#differential-privacy-budget)
4. [Federated Learning](#federated-learning)
5. [mTLS Device Identity](#mtls-device-identity)
6. [API Specifications](#api-specifications)
7. [Data Schemas](#data-schemas)
8. [Failure Modes & Recovery](#failure-modes--recovery)

---

## Consent Engine

### State Machine

Each consent grant transitions through well-defined states:

```
        ┌─────────────────┐
        │    PENDING      │  (subject approved; not yet active)
        └────────┬────────┘
                 │ (clock reaches starts_at)
                 ▼
        ┌─────────────────┐
        │    ACTIVE       │  (subject can be served inferences)
        └────┬───────┬────┘
             │       │
        (revoked)  (expires)
             │       │
             ▼       ▼
        ┌─────────────────┐
        │   REVOKED  /    │  (terminal; no inferences allowed)
        │   EXPIRED       │
        └─────────────────┘
```

### Grant Lifecycle

**Creation:**
1. Subject initiates grant request via web UI or mobile app (mTLS-verified, user-authenticated)
2. Subject specifies: model ID, purpose, scope (inference / training / both), duration (TTL)
3. Subject optionally provides context (e.g., "I'm enrolling in the Attention Study")
4. System generates a unique `grant_id` (UUID)
5. Grant is appended to the consent ledger in `PENDING` state
6. Subject receives confirmation (email + in-app notification)

**Activation:**
- If `starts_at == now`, grant is `ACTIVE` immediately
- Otherwise, grant becomes `ACTIVE` at the scheduled time (subject can schedule for the future)
- No inferences are served until `ACTIVE`

**Revocation:**
- Subject or platform can revoke at any time (subject has always-on right)
- Revocation is appended to ledger as a new record: `{ type: "revocation", grant_id: "...", revoked_at: now, revoked_by: subject_id }`
- Future inferences for this grant are denied immediately
- In-flight inferences (already being processed) complete, but results are not returned to the requester

**Expiration:**
- Grant expires at `expires_at` timestamp
- Expired grants are treated the same as revoked grants
- Subject can request renewal (generates a new grant; old one is archived)

### Consent Verification at Inference Time

**Pseudocode:**
```go
func VerifyConsent(subjectID, modelID, purpose string) (ConsentStatus, error) {
  // 1. Fetch the active grant from the ledger
  grant := consentLedger.GetActiveGrant(subjectID, modelID, purpose)
  
  if grant == nil {
    return DENIED, nil  // No active grant
  }
  
  // 2. Check state transitions (double-check in case of clock skew)
  if grant.ExpiresAt < now() {
    return EXPIRED, nil
  }
  
  if grant.StartsAt > now() {
    return NOT_YET_ACTIVE, nil
  }
  
  // 3. Check if a revocation exists in the ledger *after* this grant
  if consentLedger.HasRevocationAfter(grant.ID, grant.CreatedAt) {
    return REVOKED, nil
  }
  
  // 4. Check differential privacy budget
  budgetStatus := privacyBudget.CheckRemaining(subjectID)
  if budgetStatus.Remaining <= 0 {
    return BUDGET_EXHAUSTED, nil
  }
  
  return ACTIVE, nil
}
```

**Performance:**
- Consent checks are **O(log N)** where N is the number of grants for that subject (using indexed lookups)
- Cache-friendly: result is cached for 60 seconds (same subject + model + purpose)
- Cache invalidation: on revocation or expiration, the cache key is immediately evicted

### Ledger Schema

The consent ledger is an append-only log. Each entry is JSON (for readability) and can be streamed to binary format for efficiency.

**Grant Entry:**
```json
{
  "type": "grant",
  "grant_id": "g-550e8400-e29b-41d4-a716-446655440000",
  "subject_id": "subj-7f3a9b2c",
  "model_id": "mental-state-classifier@v2.3",
  "purpose": "attention/fatigue research",
  "scope": ["inference"],
  "created_at": "2026-06-24T10:30:00Z",
  "starts_at": "2026-06-24T10:30:00Z",
  "expires_at": "2026-07-24T10:30:00Z",
  "context": "subject enrolled in Attention Study, cohort A",
  "granted_by": "subject_id",
  "approval_session_id": "sess-abc123def456",
  "approval_ip": "102.89.34.x",
  "approval_device_fingerprint": "mobile-ios-14-safari",
  "previous_hash": "sha256:...",
  "hash": "sha256:..."
}
```

**Revocation Entry:**
```json
{
  "type": "revocation",
  "revocation_id": "rv-550e8400-e29b-41d4-a716-446655440001",
  "grant_id": "g-550e8400-e29b-41d4-a716-446655440000",
  "subject_id": "subj-7f3a9b2c",
  "revoked_at": "2026-06-25T14:22:15Z",
  "revoked_by": "subject_id",
  "reason": "subject-initiated",
  "previous_hash": "sha256:...",
  "hash": "sha256:..."
}
```

**Hash Chain:**
Each entry's `hash` field is:
```
hash(entry) = SHA256(
  concat(
    entry.type,
    entry.created_at,
    entry.grant_id or entry.revocation_id,
    entry.subject_id,
    previous_hash
  )
)
```

On startup, the system verifies the entire chain: `hash[i+1].previous_hash == hash[i].hash` for all entries. If any link is broken, the ledger is corrupted and the system alerts.

---

## Storage Layer

### Append-Only Encrypted Log

**Design:**
The storage layer is a write-ahead log (WAL) + index. Every sample or record is immutable once written.

**Layout:**
```
/var/lib/synapse/storage/
├── subjects/
│   ├── subj-7f3a9b2c/
│   │   ├── wal.log              # append-only WAL, encrypted
│   │   ├── wal.index            # offset index for fast seeks
│   │   ├── metadata.json        # subject metadata (key material, created_at)
│   │   └── checksum.sha256      # rolling checksum for tamper detection
│   ├── subj-abc123/
│   └── ...
└── consent/
    └── ledger.log               # consent ledger, append-only
    └── ledger.index
    └── ledger.hash              # current ledger root hash
```

### Sample Record Format

**In the WAL:**
```json
{
  "record_type": "sample",
  "sample_id": "samp-xyz-0001",
  "subject_id": "subj-7f3a9b2c",
  "device_id": "device-01",
  "timestamp_ms": 1719226200000,
  "eeg_channels": {
    "fp1": 4.2,
    "fp2": 3.8,
    "...": 0.0
  },
  "sample_rate_hz": 250,
  "device_signature": "base64:...",
  "received_at": "2026-06-24T10:30:00Z",
  "encrypted_payload": "base64:aes256gcm_ciphertext",
  "nonce": "base64:gcm_nonce",
  "auth_tag": "base64:gcm_auth_tag",
  "version": 1
}
```

**Encryption:**
- Per-subject key material (derived from subject's enrollment key + a random salt)
- Algorithm: AES-256-GCM
- Nonce: 12-byte random nonce (never reused for the same key)
- Auth tag: 16-byte GCM authentication tag (catches tampering)
- The entire JSON payload is encrypted (sample values + metadata); only record_type, sample_id, and subject_id are in the clear (needed for indexing)

### Per-Subject Key Isolation

**Key Hierarchy:**
```
Platform Master Key (KMS-managed)
  └─ Subject Envelope Key (encrypted under Platform Key)
       └─ Subject Data Key (used for AES-256-GCM)
```

**Key Rotation:**
- Subject data key rotates monthly (or on-demand)
- Old records are *not* re-encrypted; the system maintains historical key material
- On key rotation, a new envelope key entry is appended to the subject's metadata

### WAL Durability

**Write Path:**
1. Record arrives at gateway
2. Record is encrypted
3. Record is serialized to the WAL file
4. WAL file is fsync'd (forced to disk)
5. Only then is ACK sent to the client

**Crash Recovery:**
- On restart, the system reads the WAL and verifies every record's auth tag
- If a record's auth tag fails, the WAL is truncated to the last valid record
- An alert is raised (potential corruption or tampering)

---

## Differential Privacy Budget

### Budget Tracking

Each subject has a **privacy budget** (epsilon, δ):
- `epsilon_total`: Total budget per epoch (e.g., 1.0 per month)
- `epsilon_spent`: Running total of epsilon spent on inferences and training
- `epsilon_remaining`: `epsilon_total - epsilon_spent`
- `delta`: Failure probability (e.g., 1e-5); fixed per subject

**Budget per Inference:**
```
epsilon_cost = clip_norm / (number_of_samples_in_training_set)
```

For an inference request:
- The model has a known `L2_clip_norm` (e.g., 1.0 for attention/fatigue models)
- The budget cost is: `epsilon_cost = L2_clip_norm / (number of training samples)`
- If subject's `epsilon_remaining - epsilon_cost >= 0`, the inference is allowed
- The spent amount is logged with the prediction

**Budget Reset:**
- Budgets reset monthly (configurable epoch)
- On reset, `epsilon_spent` is zeroed; `epsilon_remaining = epsilon_total`
- Historical spent data is retained for audit purposes

### Differential Privacy at Inference

**Laplace Mechanism:**
```
noisy_prediction = true_prediction + Laplace(0, sensitivity / epsilon)
```

For a binary classification (attention / fatigue):
- Sensitivity = 1.0 (max change from one sample)
- Scale parameter = 1.0 / epsilon_spent_so_far
- Noise is sampled from Laplace and added to the logits before softmax

**Scale grows as budget shrinks:**
- After 10% of budget spent: scale = 10.0 (high noise)
- After 50% of budget spent: scale = 2.0 (moderate noise)
- After 90% of budget spent: scale = 1.1 (low noise; last few queries are nearly accurate)
- After 100% of budget spent: inference denied

### Federated Learning & DP

**Per-Node Clipping:**
Each node clips gradients per-sample:
```
clipped_gradient = gradient * min(1, clip_norm / ||gradient||_2)
```

**Noise Addition (Server-Side):**
After aggregating clipped gradients from K nodes:
```
noisy_aggregate = aggregate + Laplace(0, K * clip_norm / epsilon)
```

The epsilon budget for training is *separate* from inference epsilon. A subject might have `epsilon_training=2.0` and `epsilon_inference=1.0` per month.

---

## Federated Learning

### Orchestration

**Round Lifecycle:**

1. **Initialization**: Orchestrator (Python service) selects nodes and initiates a round
   - Selects N nodes from those that have opted into training
   - Sends model snapshot and hyperparameters to each node
   - Each node starts local training

2. **Local Training** (parallel, on each node):
   - Node loads the model
   - Node trains on local data for E epochs
   - After each epoch, gradients are clipped and summed
   - Node computes DP gradient (adds Laplace noise)
   - Node encrypts the DP gradient and sends to aggregator

3. **Aggregation** (server-side):
   - Aggregator collects DP gradients from nodes
   - Aggregator computes secure average: `sum(gradient) / N`
   - Aggregator updates the global model
   - Aggregator publishes the new model snapshot

4. **Completion**:
   - Orchestrator verifies that N nodes completed
   - Round is marked as complete; model version is incremented
   - New model is deployed to inference services

**Timeout & Fault Tolerance:**
- Each node has T_node seconds to send its gradients (e.g., 3600s)
- If a node doesn't respond, it's marked as failed
- Orchestrator waits for max(N-1, 3) nodes to succeed (tolerance for 1 node failure)
- If fewer nodes succeed, the round is aborted and retried later

### Model Versioning & Deployment

**Model Format:**
```
models/mental-state-classifier/
├── v1.0/
│   ├── model.pkl              # trained weights
│   ├── hyperparams.json       # learning rate, regularization, etc.
│   ├── training_metadata.json # training set, date, nodes involved
│   ├── dp_params.json         # epsilon, delta, clip_norm used
│   └── signature.sha256       # immutable after deployment
├── v2.0/
├── v2.1/
└── v2.3/                      # current version
```

**Immutability:**
- Once a model version is deployed, its signature is locked
- Code cannot change model weights in-place
- If retraining is needed, a new version is created

### Secure Aggregation (Future)

Post-MVP: Instead of a central aggregator seeing all gradients, use cryptographic aggregation:
- Each node encrypts its gradient under a threshold encryption scheme
- No single party can decrypt individual gradients
- Aggregator computes the sum without decryption (homomorphic properties)
- Only the final sum is decrypted (which reveals aggregate DP gradient, not individual gradients)

---

## mTLS Device Identity

### Device Enrollment

**Out-of-Band:**
1. Subject enrolls in the platform via web UI
2. Subject downloads a provisioning token (short-lived, 1-time use)
3. Subject opens the edge application on their device
4. Edge app exchanges provisioning token for a certificate signing request (CSR)
5. Platform's CA signs the CSR, returning an X.509 certificate
6. Edge app stores the certificate and private key in device secure storage (TEE / Keychain)

**Certificate Format:**
```
Subject: CN=device-01, O=SYNAPSE-AI, C=NG
Issuer: CN=SYNAPSE-AI-CA, O=SYNAPSE-AI, C=NG
Not Before: 2026-06-24 10:00:00
Not After: 2027-06-24 10:00:00  (1 year)
Public Key: EC P-256
Serial: 550e8400-e29b-41d4-a716-446655440000
```

### Device Authentication

**On Every Connection:**
- Edge device initiates mTLS handshake with the gateway
- Gateway verifies the certificate chain (root CA → intermediate → device cert)
- Gateway checks the certificate's `NotAfter` time
- Gateway verifies the device cert is not in the revocation list (CRL)

**Per-Sample Signing:**
Each EEG sample is signed with the device's private key:
```
signature = ECDSA_Sign(
  device_private_key,
  hash(sample_payload)
)
```

Gateway verifies:
```
if !ECDSA_Verify(device_public_key_from_cert, signature, sample_payload) {
  reject_sample()
}
```

### Certificate Revocation

**When a device is compromised:**
- Subject initiates revocation via web UI
- Revocation request is appended to a certificate revocation list (CRL)
- Gateway periodically fetches updated CRL (every 10 minutes)
- Revoked certificates are rejected at mTLS handshake time

---

## API Specifications

### Ingestion API (gRPC)

**Service: `IngestService`**

```protobuf
service IngestService {
  // Stream EEG samples to secure ingestion
  rpc StreamSamples(stream EEGSample) returns (stream IngestAck);
}

message EEGSample {
  string device_id = 1;
  string subject_id = 2;  // populated by gateway based on mTLS cert
  int64 timestamp_ms = 3;
  map<string, float> channels = 4;  // e.g., { "fp1": 4.2, "fp2": 3.8 }
  int32 sample_rate_hz = 5;
  bytes device_signature = 6;  // ECDSA signature of the sample payload
  bytes encrypted_payload = 7;  // AES-256-GCM encrypted EEGSample
}

message IngestAck {
  string sample_id = 1;
  bool accepted = 2;
  string error_message = 3;  // if accepted=false
  int64 received_at_unix_ms = 4;
}
```

### Consent API (gRPC)

```protobuf
service ConsentService {
  // Create a new consent grant
  rpc CreateGrant(CreateGrantRequest) returns (CreateGrantResponse);
  
  // List active grants for a subject
  rpc ListGrants(ListGrantsRequest) returns (ListGrantsResponse);
  
  // Revoke a specific grant
  rpc RevokeGrant(RevokeGrantRequest) returns (RevokeGrantResponse);
  
  // Check if a (subject, model, purpose) tuple is consented
  rpc VerifyConsent(VerifyConsentRequest) returns (VerifyConsentResponse);
}

message CreateGrantRequest {
  string subject_id = 1;
  string model_id = 2;
  string purpose = 3;
  repeated string scope = 4;  // ["inference"] or ["training"] or both
  int32 ttl_days = 5;
  string context = 6;  // optional; human-readable context
}

message CreateGrantResponse {
  string grant_id = 1;
  string status = 2;  // "PENDING" or "ACTIVE"
  int64 created_at_unix_ms = 3;
  int64 expires_at_unix_ms = 4;
}

message VerifyConsentRequest {
  string subject_id = 1;
  string model_id = 2;
  string purpose = 3;
  string scope = 4;  // "inference" or "training"
}

message VerifyConsentResponse {
  string status = 1;  // "ACTIVE", "DENIED", "EXPIRED", "REVOKED", "BUDGET_EXHAUSTED"
  string reason = 2;
  bool allowed = 3;
}
```

### Inference API (gRPC)

```protobuf
service InferenceService {
  rpc Infer(InferenceRequest) returns (InferenceResponse);
}

message InferenceRequest {
  string subject_id = 1;
  string model_id = 2;  // "mental-state-classifier@v2.3"
  string requester = 3;  // mTLS-verified identity of the calling service
  string purpose = 4;  // must match an active consent grant
}

message InferenceResponse {
  map<string, double> prediction = 1;  // { "attention": 0.71, "stress": 0.82 }
  string consent_status = 2;  // "ACTIVE", "DENIED", etc.
  double epsilon_spent = 3;
  double epsilon_remaining = 4;
  string audit_hash = 5;  // Merkle root of the prediction provenance record
  bool served = 6;  // false if consent, DP budget, or other check failed
  string error_message = 7;
}
```

### Audit API (gRPC)

```protobuf
service AuditService {
  rpc GetPrediction(GetPredictionRequest) returns (PredictionRecord);
  rpc ListPredictions(ListPredictionsRequest) returns (stream PredictionRecord);
  rpc GetConsentLedger(GetConsentLedgerRequest) returns (stream ConsentLedgerEntry);
}

message PredictionRecord {
  string prediction_id = 1;
  map<string, double> prediction = 2;
  string model_id = 3;
  string subject_id = 4;
  string requester = 5;
  int64 timestamp_unix_ms = 6;
  string consent_grant_id = 7;
  string consent_status = 8;
  double epsilon_spent = 9;
  string audit_hash = 10;  // SHA256 hash of this record
}
```

---

## Data Schemas

### Subject Metadata

```json
{
  "subject_id": "subj-7f3a9b2c",
  "created_at": "2026-06-01T08:00:00Z",
  "enrollment_status": "active",
  "devices": [
    {
      "device_id": "device-01",
      "device_name": "Personal EEG Headset",
      "certificate_cn": "device-01",
      "enrolled_at": "2026-06-01T08:00:00Z",
      "last_used": "2026-06-24T10:30:00Z",
      "status": "active"
    }
  ],
  "privacy_settings": {
    "epsilon_total_per_month": 1.0,
    "delta": 1e-5,
    "allow_federated_training": true,
    "allow_model_publishing": false
  },
  "contact_email": "subject@example.com",
  "contact_phone": "+234..."
}
```

### Prediction Provenance Record

```json
{
  "prediction_id": "pred-9c2e",
  "subject_id": "subj-7f3a9b2c",
  "model_id": "mental-state-classifier@v2.3",
  "model_training_set": "public-eeg-2025-attention",
  "prediction": {
    "attention": 0.71,
    "fatigue": 0.18,
    "stress": 0.11
  },
  "prediction_timestamp": "2026-06-24T09:12:33Z",
  "requester_id": "research-lab-01",
  "requester_mTLS_cert": "...",
  "purpose": "attention/fatigue research",
  "consent": {
    "grant_id": "g-550e8400-e29b-41d4-a716-446655440000",
    "status": "active",
    "granted_at": "2026-06-24T09:00:00Z",
    "expires_at": "2026-07-24T09:00:00Z"
  },
  "privacy_budget": {
    "epsilon_spent_on_this_request": 0.1,
    "epsilon_total_remaining_after": 0.9
  },
  "latency_ms": 45,
  "inference_engine": "onnxruntime",
  "audit_hash": "sha256:abcd1234...",
  "previous_audit_hash": "sha256:..."
}
```

---

## Failure Modes & Recovery

### Failure Mode 1: Consent Ledger Becomes Corrupted

**Symptom:** Hash chain verification fails on startup

**Recovery:**
1. System enters read-only mode
2. Alert is raised (PagerDuty, email to on-call)
3. On-call engineer inspects the ledger
4. Options:
   - Truncate to last valid record (loses recent grants/revocations; risky)
   - Restore from backup (requires recent backups; replay transaction log)
   - Full rebuild from append-only log snapshots (time-consuming)
5. Once recovered, exit read-only mode

**Prevention:**
- Daily backup of ledger
- Weekly verification of hash chain (cron job)
- Monitoring: alert if hash chain verification ever fails

### Failure Mode 2: Storage Encryption Key is Lost

**Symptom:** Subject's data key is missing; encrypted samples cannot be decrypted

**Recovery:**
1. Check KMS (key management service) for historical key versions
2. If KMS has it, retrieve and restore to local key store
3. If KMS doesn't have it, data is unrecoverable
4. Alert subject; offer manual review of their data

**Prevention:**
- Key material is replicated to multiple KMS instances (geo-redundant)
- Key versioning: every key rotation is logged
- Audit log of all key access (who accessed what, when)

### Failure Mode 3: Node Failure During Federated Round

**Symptom:** A node drops mid-training; orchestrator can't collect its gradients

**Recovery:**
1. Orchestrator waits for node timeout (default: 3600s)
2. If N-1 ≥ 3 (or configured min), aggregate from remaining nodes
3. If N-1 < 3, abort the round and notify trainers
4. Retried in the next round; no data loss

**Prevention:**
- Nodes checkpoint their gradients to disk every epoch
- If a node restarts, it can resume from the last checkpoint
- Orchestrator replicates the aggregation state (can resume if it crashes)

### Failure Mode 4: Inference Service Crashes & Predictions Are Lost

**Symptom:** Inference service crashes before writing prediction to audit log

**Recovery:**
1. Predictions are cached in memory with a TTL
2. If inference crashes, in-memory predictions are lost (acceptable; inference is a read)
3. If audit log write crashes, prediction is not recorded (audit trail gap)
4. Detection: audit gap (prediction_id sequence is not monotonic)
5. Recovery: rebuild missing predictions from inference request logs (if available)

**Prevention:**
- Write predictions to audit log *before* responding to requester
- Audit log is persisted to multiple disks (RAID)
- Monitoring: alert if audit sequence gaps are detected

### Failure Mode 5: Subject's Privacy Budget Is Exhausted

**Symptom:** Subject has spent ε=1.0; no more inferences allowed

**Recovery:**
1. Subject is notified (email)
2. Subject can request an early reset (manager approval required)
3. Or subject waits for the monthly automatic reset
4. No data loss; this is a feature, not a failure

**Prevention:**
- Alert subject at ε=0.7, ε=0.9, ε=0.95
- Suggest pausing inferences to preserve budget
- Offer budget visualization (how much remaining, burn rate)

---

## Implementation Roadmap & Phase Gates

### Phase 1: Foundation (Weeks 1-6)
- [ ] Storage layer (WAL + encryption)
  - [ ] Per-subject key isolation
  - [ ] Append-only log + index
  - [ ] WAL durability & crash recovery
- [ ] Consent engine (in-memory, simple)
  - [ ] Grant creation & revocation
  - [ ] Hash-chained ledger
  - [ ] Synchronous consent verification
- [ ] mTLS device identity
  - [ ] Device enrollment
  - [ ] Certificate validation at gateway

**Gate:** All unit tests pass; chaos test for consent bypass fails (as expected)

### Phase 2: Inference & Observability (Weeks 7-10)
- [ ] Inference service
  - [ ] Consent-gated inference
  - [ ] DP budget tracking
  - [ ] Prediction provenance logging
- [ ] Metrics & monitoring
  - [ ] Prometheus exporters
  - [ ] Grafana dashboards
  - [ ] Structured logging

**Gate:** Inference requests are served; consent denials are logged; DP budget is tracked

### Phase 3: Federated Learning (Weeks 11-14)
- [ ] Federated orchestrator
  - [ ] Model distribution
  - [ ] Gradient aggregation
  - [ ] DP gradient noise
- [ ] Fault tolerance
  - [ ] Node timeout & recovery
  - [ ] Aggregator checkpointing

**Gate:** A full federated round completes; DP noise is verified statistically

### Phase 4: Hardening & Verification (Weeks 15-18)
- [ ] Chaos testing suite
  - [ ] Consent bypass attempts
  - [ ] Tampering detection
  - [ ] Node failures
- [ ] Security audit
  - [ ] Code review
  - [ ] Threat model verification

**Gate:** All chaos tests pass; no audit findings

---

## Configuration & Tuning

### Critical Parameters

```yaml
gateway:
  max_request_latency_ms: 5000
  consent_check_cache_ttl_s: 60
  rate_limit_per_device: 1000  # samples/sec
  
storage:
  wal_sync_interval_ms: 100
  key_rotation_interval_days: 30
  
privacy:
  epsilon_per_subject_per_month: 1.0
  delta: 1e-5
  laplace_scale_computation: "1.0 / epsilon_spent"
  
federated_learning:
  min_nodes_for_round: 3
  node_timeout_s: 3600
  gradient_clip_norm: 1.0
  dp_epsilon_training: 2.0  # separate from inference epsilon
  
audit:
  hash_chain_verification_interval_hours: 24
  retention_period_years: 7
```

---

**Status:** Ready for engineering review and detailed implementation planning.
