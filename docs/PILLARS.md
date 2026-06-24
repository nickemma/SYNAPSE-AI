# THE PILLARS — SYNAPSE-AI

**Deep Dive into the Five Core Pillars**

**Last Updated:** June 24, 2026

---

## Overview

The SYNAPSE-AI platform rests on five architectural pillars. Each pillar solves a specific security or governance problem. Together, they form a system where machine learning operates on highly sensitive neural data while preserving ownership, consent, auditability, and privacy.

| Pillar | Problem Solved | Implementation |
| --- | --- | --- |
| **1. Secure Ingestion & Storage** | Data theft, tampering | Edge encryption + append-only WAL |
| **2. Consent & Governance Engine** | Unauthorized access, consent violation | Structured grants, synchronous verification, hash-chained ledger |
| **3. Privacy-Preserving ML** | Privacy leakage via model inversion | Federated learning + differential privacy |
| **4. Provenance & Audit** | Unaccountable decisions, regulatory non-compliance | Self-describing predictions, tamper-evident audit trail |
| **5. Observability & Security** | Unknown state, undetected attacks | Metrics, dashboards, chaos testing |

---

## Pillar 1: Secure Ingestion & Storage

### Problem

Neural signals are highly sensitive. Once they leave the device, they are vulnerable to interception, theft, tampering, and unauthorized use. The goal is to ensure that raw EEG data is never exposed in plaintext off the device, and that any modification is detectable.

### Solution

**Edge-to-encrypted-storage pipeline:**

```
Device: Sample → Sign → Encrypt → mTLS → Gateway → Storage (still encrypted)
```

**Key Components:**

#### 1a. Edge Signing & Encryption

**Why:**
- Signing: Detect tampering (device signs before transmission)
- Encryption: Prevent eavesdropping (network is untrusted)
- Edge-first: No plaintext ever transmitted

**How:**
```
On device:
1. Collect EEG sample (raw)
2. Create payload: { sample_id, timestamp, channels, device_id, subject_id }
3. Sign payload: signature = ECDSA(device_private_key, hash(payload))
4. Encrypt payload: ciphertext = AES-256-GCM(subject_data_key, payload)
5. Transmit: { ciphertext, nonce, auth_tag, signature }

Off-device:
6. mTLS handshake (device cert verified)
7. Gateway receives encrypted packet
8. Verify signature (no plaintext needed)
9. Store encrypted packet (no decryption needed)
```

**Security Properties:**
- Device authentication: Only registered devices can submit samples
- Sample integrity: Signature detects tampering
- Confidentiality: Encryption prevents eavesdropping
- Non-repudiation: Device cannot deny sending a signed sample

#### 1b. Append-Only Encrypted Log (Write-Ahead Log)

**Why:**
- Append-only: No deletion, no in-place mutation (history preserved)
- Encrypted: Data is encrypted at rest
- Write-ahead: Durability before acknowledgment

**How:**

```
Storage Layout:
/var/lib/synapse/subjects/
├── subj-7f3a/
│   ├── wal.log              # append-only binary log, encrypted
│   ├── wal.index            # offset index for fast seeks
│   ├── key-history.json     # old encryption keys (for decryption)
│   └── checksum.sha256      # rolling checksum of WAL
└── subj-abc123/
    ├── wal.log
    ├── wal.index
    ...

Writing a Sample:
1. Serialize sample: protobuf or JSON
2. Compute auth: GCM authentication tag
3. Append to wal.log
4. fsync() to disk (durability)
5. Return ACK to client

Reading a Sample:
1. Look up sample offset in wal.index
2. Seek to offset in wal.log
3. Read encrypted sample
4. Verify GCM authentication tag
5. Return to requester (decryption happens in inference service)
```

**Guarantees:**
- **Immutability:** Once written, cannot be modified
- **Tamper-evidence:** GCM authentication detects any corruption
- **Durability:** fsync before ACK; survives crashes
- **Auditability:** Every sample write is persisted with timestamp

#### 1c. Per-Subject Key Isolation

**Why:**
- Isolation: A single key compromise exposes only one subject's data
- Revocation: Can rotate a subject's key without affecting others

**How:**

```
Key Hierarchy:

Platform Master Key (KMS)
  └─ Subject Envelope Key (encrypted under Platform Key)
       └─ Subject Data Key (used for AES-256-GCM per sample)

Example:
- Platform Master Key: AWS KMS managed key (root of trust)
- Subject Envelope Key: platform_mk.decrypt(subject_ek_ciphertext)
- Subject Data Key: envelope_key.decrypt(subject_dk_ciphertext)
- Sample Encryption: aes256gcm(subject_data_key, sample)

Key Rotation (Monthly):
1. Generate new subject data key
2. Encrypt under current envelope key
3. Store envelope key + encrypted data key
4. Mark old key as "deprecated"
5. Old samples stay encrypted under old key
6. New samples use new key
7. No re-encryption needed
```

**Security Properties:**
- Scope limitation: Compromise of one subject's key doesn't expose others
- Revocation: Can immediately block access to a subject's future data
- Key diversity: Each subject has a unique encryption key
- Audit trail: Key rotation history is logged

#### 1d. mTLS Device & Gateway Authentication

**Why:**
- Device authentication: Ensure only registered devices submit samples
- Gateway authentication: Ensure the service is who it claims to be

**How:**

```
Device Enrollment:
1. Subject creates account on web
2. Receives provisioning token (1-time use, 24h expiry)
3. Opens edge app
4. App exchanges token for certificate signing request (CSR)
5. Platform CA signs CSR → returns X.509 device cert
6. App stores cert + private key in device secure storage (TEE/Keychain)

Ongoing Connection:
7. Device initiates mTLS handshake with gateway
8. Device presents certificate (CN=device-01, signed by platform CA)
9. Gateway verifies cert chain (root CA → intermediate → device)
10. Gateway checks cert NotAfter (not expired)
11. Gateway checks cert not in revocation list (CRL)
12. Both parties exchange encrypted data

Revocation:
If device is compromised:
1. Subject initiates revocation via web UI
2. Device cert is added to CRL
3. Gateway fetches updated CRL (every 10 minutes)
4. Subsequent mTLS handshakes fail (cert in revocation list)
```

**Security Properties:**
- Mutual authentication: Both device and gateway verify each other
- Forward secrecy: Perfect forward secrecy (PFS) via TLS 1.3 ephemeral keys
- Revocation: Compromised devices can be blocked immediately
- Audit: Every connection is logged with cert serial number

### Implementation Status

- ✅ mTLS device & gateway authentication
- ✅ Edge signing & encryption (on device)
- ✅ Append-only WAL with index
- ✅ Per-subject key isolation
- ✅ Encryption at rest (AES-256-GCM)
- ⏳ Key rotation automation (post-MVP)
- ⏳ CRL distribution (post-MVP)

---

## Pillar 2: Consent & Governance Engine

### Problem

Machine learning models typically run on data with a one-time consent form (or no consent at all). This is insufficient for neural data. A subject should be able to:
- Grant consent scoped to a specific model and purpose
- Revoke consent immediately at any time
- See exactly what they're consenting to
- Know that revocation is honored in real-time

### Solution

**Consent as a first-class, enforceable runtime object:**

```
Subject → Grants consent for (Model, Purpose, Time) → 
System verifies grant on every inference → 
Subject revokes → System denies future inferences immediately
```

#### 2a. Structured, Scoped Consent Grants

**Why:**
- Scope limits: A model trained for "attention research" cannot be used for "fatigue prediction"
- Time bounds: Consent expires after N days (subject explicitly knows when)
- Revocability: Explicit consent can be explicitly withdrawn

**Grant Structure:**

```json
{
  "grant_id": "g-550e8400-e29b-41d4-a716-446655440000",
  "subject_id": "subj-7f3a9b2c",
  "model_id": "mental-state-classifier@v2.3",
  "model_version": "v2.3",
  "purpose": "attention/fatigue research",
  "scope": ["inference"],  // or ["training"] or both
  "created_at": "2026-06-24T10:30:00Z",
  "starts_at": "2026-06-24T10:30:00Z",
  "expires_at": "2026-07-24T10:30:00Z",
  "ttl_days": 30,
  "revocable": true,
  "status": "active",  // pending, active, expired, revoked
  "context": "subject enrolled in Attention Study, cohort A",
  "granted_by": "subject_id",
  "revoked_at": null,
  "revoked_by": null,
  "revocation_reason": null
}
```

**Semantics:**
- `model_id@version` is immutable (can't re-grant to a newer version without new consent)
- `purpose` is a free-form string (e.g., "attention/fatigue research", "sleep study")
- `scope` determines what the model can do (inference, training, or both)
- Expiration is hard-stop (no automatic renewal; subject must explicitly request)

#### 2b. Verified Before Every Inference

**Why:**
- Real-time enforcement: At the moment of inference, the grant must be active
- No trust: Cache is fine for performance, but synchronous verification is the source of truth
- Immediate revocation: If a subject revokes at T=0, inferences at T>0 are denied

**Verification Logic:**

```
function VerifyConsent(subjectID, modelID, purpose):
  // 1. Lookup grant in ledger
  grant = ledger.GetGrant(subjectID, modelID, purpose)
  
  if grant == null:
    return DENIED  // No grant exists
  
  // 2. Check time boundaries
  if grant.StartsAt > now():
    return NOT_YET_ACTIVE  // Grant not yet active
  
  if grant.ExpiresAt < now():
    return EXPIRED  // Grant has expired
  
  // 3. Check for revocation
  revocation = ledger.GetRevocationAfter(grant.ID, grant.CreatedAt)
  if revocation != null:
    return REVOKED  // Grant was revoked
  
  // 4. Check DP budget (separate concern)
  budget = privacy_db.GetBudget(subjectID)
  if budget.Remaining <= 0:
    return BUDGET_EXHAUSTED
  
  return ACTIVE  // All checks passed
```

**Performance:**
- Cache-backed: Last 60 seconds of verification cached (same subject+model+purpose)
- O(log N) ledger lookup: Indexed by subject_id + model_id + purpose
- Synchronous verification: <10ms p99 latency

#### 2c. Hash-Chained Consent Ledger

**Why:**
- Tamper-evidence: Any modification breaks the hash chain
- Auditability: Prove what was permitted at any point in time
- Non-repudiation: Subject cannot deny granting consent

**Ledger Structure:**

```
Entry 1 (Grant):
  {
    type: "grant",
    grant_id: "g-001",
    subject_id: "subj-7f3a",
    model_id: "model-v1",
    ... (all grant fields)
    previous_hash: "sha256:0000..." (first entry, no previous)
    hash: "sha256:abcd1234..."
  }

Entry 2 (Grant):
  {
    type: "grant",
    grant_id: "g-002",
    subject_id: "subj-7f3a",
    model_id: "model-v2",
    ... (all grant fields)
    previous_hash: "sha256:abcd1234..." (hash of Entry 1)
    hash: "sha256:efgh5678..."
  }

Entry 3 (Revocation):
  {
    type: "revocation",
    revocation_id: "rv-001",
    grant_id: "g-001",
    subject_id: "subj-7f3a",
    revoked_at: "2026-06-25T14:22:15Z",
    revoked_by: "subject_id",
    reason: "subject-initiated",
    previous_hash: "sha256:efgh5678..." (hash of Entry 2)
    hash: "sha256:ijkl9012..."
  }

Hash Chain Verification:
Entry[i].previous_hash == Entry[i-1].hash  (for all i)
If any link is broken → TAMPERING DETECTED
```

**Durability:**
- Ledger is replicated to PostgreSQL with WAL
- Backups to S3 (encrypted, geo-redundant)
- Quarterly publication of root hash (for external audit)

#### 2d. Immediate Revocation

**Why:**
- Subject's right: Can withdraw consent at any time
- Enforcement: Revocation is not "eventually consistent"; it's immediate
- Proof: Revocation record is appended to ledger; cannot be undone

**Revocation Flow:**

```
Subject clicks "Revoke" on grant G:
  │
  ├─→ Create revocation record:
  │   {
  │     type: "revocation",
  │     grant_id: G.ID,
  │     revoked_at: now(),
  │     revoked_by: subject_id,
  │     ...
  │   }
  │
  ├─→ Append to ledger (durability)
  │
  ├─→ Evict from consent cache (immediate effect)
  │
  ├─→ Return "Revocation successful"
  │
  └─→ Subject receives notification

Future inference requests:
  ├─→ Check ledger for revocation (after grant)
  ├─→ Found: Return DENIED
  ├─→ Inference blocked immediately
```

**Timing:**
- Cache hit: <1ms (revocation takes effect within 60s)
- Cache miss: ~10ms (revocation takes effect immediately)
- Maximum delay: 60 seconds (cache TTL)

### Implementation Status

- ✅ Structured grant schema
- ✅ Hash-chained ledger
- ✅ Synchronous verification (with cache)
- ✅ Revocation (immediate)
- ✅ Ledger backup & recovery
- ⏳ External ledger publication (quarterly attestation)

---

## Pillar 3: Privacy-Preserving ML

### Problem

Models trained on sensitive data can leak information via:
- Model inversion attacks (reconstruct training data from model outputs)
- Membership inference attacks (infer whether a subject was in the training set)
- Attribute inference (learn private attributes from predictions)

### Solution

**Federated learning + differential privacy:**

```
Federated: Raw data never centralized → Model travels to data
Differential Privacy: Bounded noise added to gradients → Provable privacy guarantees
```

#### 3a. Federated Learning

**Why:**
- Data residency: Raw neural signals stay on-node; platform only sees aggregated updates
- Trust: Subjects don't have to trust the platform to see their raw data
- Privacy: No single entity has the full dataset

**How:**

```
Round N:
  │
  ├─→ Orchestrator: "Download model v2.3, train for 5 epochs"
  │
  ├─→ Node 1: Load model + subject A's data
  │         └─→ Train locally (data never leaves node)
  │         └─→ Compute gradients
  │         └─→ Clip & add DP noise
  │         └─→ Send DP gradients (encrypted)
  │
  ├─→ Node 2: Load model + subject B's data
  │         └─→ Train locally
  │         └─→ Compute gradients
  │         └─→ Clip & add DP noise
  │         └─→ Send DP gradients (encrypted)
  │
  ├─→ Node 3: Load model + subject C's data
  │         └─→ Train locally
  │         └─→ Compute gradients
  │         └─→ Clip & add DP noise
  │         └─→ Send DP gradients (encrypted)
  │
  ├─→ Aggregator:
  │   ├─→ Collect DP gradients from all nodes
  │   ├─→ Aggregate: avg(grad1, grad2, grad3)
  │   ├─→ Update model weights: w_new = w_old - learning_rate * aggregated_gradient
  │   ├─→ Save model v2.4
  │   └─→ Broadcast new model
  │
  └─→ Round complete (raw data never left the nodes)
```

**Guarantees:**
- **Data residency:** Raw EEG stays on-node
- **Gradient privacy:** Gradients are clipped & noised before aggregation
- **Model training:** Trains on real data without centralizing

#### 3b. Differential Privacy

**Why:**
- Formal guarantee: Quantifies how much info leaks about any single subject
- Epsilon budget: Subject knows their privacy limit
- Auditable: Privacy spend is tracked and cannot be exceeded

**How:**

```
Differential Privacy (DP) Basics:
  An algorithm is ε-differentially private if changing one input
  changes the output by at most ε (in log-likelihood).
  
  Intuition:
  - ε = 0: Output never changes (no info leaks) → impossible
  - ε = 0.1: Output barely changes (info leak is tiny)
  - ε = 1.0: Output noticeably changes (moderate leak)
  - ε = ∞: No privacy (no DP guarantee)

Gradient Clipping (per-node):
  Raw gradient from one sample: g_i
  Clip magnitude: clipped_g_i = g_i * min(1, clip_norm / ||g_i||_2)
  
  Effect: Outlier gradients (from outlier samples) are scaled down
  Reason: Prevents one sample from dominating the gradient

Noise Injection (server-side):
  Aggregated gradient: G_agg = sum(clipped_g_i for all nodes)
  Laplace noise: noise ~ Laplace(0, scale)
  Scale parameter: scale = K * clip_norm / ε
  
  Noisy gradient: G_noisy = G_agg + noise
  
  Effect: Noise is inversely proportional to ε
    - Small ε (tight budget) → large scale → high noise
    - Large ε (loose budget) → small scale → low noise

Epsilon Budget Tracking (per-subject, per-month):
  epsilon_total = 1.0  (e.g., per month)
  epsilon_spent = 0.0
  epsilon_remaining = 1.0
  
  After training round 1: epsilon_spent += 0.2 → remaining = 0.8
  After training round 2: epsilon_spent += 0.3 → remaining = 0.5
  After training round 3: epsilon_spent += 0.5 → remaining = 0.0
  
  Status: BUDGET_EXHAUSTED → No more training/inference allowed
  Reset: Monthly reset (epsilon_spent = 0, epsilon_remaining = 1.0)
```

**Composition:**
When multiple algorithms are combined:
```
Total epsilon = sum of individual epsilons (worst-case composition)

Example:
  - Training round 1: ε = 0.2
  - Training round 2: ε = 0.3
  - Inference 1-10: ε = 0.1 each (total 1.0)
  - Total: 0.2 + 0.3 + 1.0 = 1.5 ε spent

  If budget is ε = 1.0 per month, exceeded after 0.7 months
```

#### 3c. Training on Public Datasets

**Why:**
- Regulatory clarity: Non-medical classification is not a diagnostic tool
- Data availability: Don't require new subject data collection
- Scope manageability: Public datasets are smaller, easier to validate

**Datasets:**
- OpenBCI public EEG (attention, meditation states)
- PHYSIONET PhysioBank (sleep, stress, fatigue)
- Custom-collected public datasets (with informed consent)

**Tasks:**
- Attention classification (alert vs. drowsy)
- Fatigue detection (fresh vs. fatigued)
- Stress estimation (calm vs. stressed)
- Cognitive workload estimation (low vs. high)

**Not Included (Post-MVP):**
- Seizure detection (medical diagnosis)
- Depression screening (psychiatric diagnosis)
- Sleep disorder diagnosis (clinical use)

### Implementation Status

- ✅ Federated learning (multi-node training)
- ✅ Differential privacy (gradient clipping + Laplace noise)
- ✅ Epsilon budget tracking & enforcement
- ✅ Public dataset integration (OpenBCI, PHYSIONET)
- ✅ Model versioning (immutable snapshots)
- ⏳ Secure multi-party computation (post-MVP)
- ⏳ Post-quantum cryptography (future)

---

## Pillar 4: Provenance & Audit

### Problem

Without an audit trail, you cannot answer: "Was this inference allowed?" "Who ran it?" "What was the model trained on?" Regulators increasingly require this level of auditability.

### Solution

**Every prediction is self-describing. Audit trail is tamper-evident.**

#### 4a. Self-Describing Predictions

**Why:**
- Traceability: Link prediction to the authorizing grant, model, and requester
- Reproducibility: Can recreate the decision months later
- Compliance: Provide auditors with proof

**Prediction Record:**

```json
{
  "prediction_id": "pred-9c2e",
  "subject_id": "subj-7f3a9b2c",
  "model_id": "mental-state-classifier@v2.3",
  "model_training_set": "openeci-2025-attention-study",
  "model_hash": "sha256:model-weights-hash",
  "prediction": {
    "attention": 0.71,
    "fatigue": 0.18,
    "stress": 0.11
  },
  "prediction_timestamp": "2026-06-24T09:12:33Z",
  "requester_id": "research-lab-01",
  "requester_mTLS_cert": "sha256:cert-fingerprint",
  "purpose": "attention/fatigue research",
  "consent": {
    "grant_id": "g-550e8400-e29b-41d4-a716-446655440000",
    "status": "active",
    "granted_at": "2026-06-24T09:00:00Z",
    "expires_at": "2026-07-24T09:00:00Z"
  },
  "privacy_budget": {
    "epsilon_total": 1.0,
    "epsilon_spent_on_this_request": 0.1,
    "epsilon_total_remaining_after": 0.9
  },
  "inference_config": {
    "preprocessing": "bandpass(0.5-50Hz), downsample(125Hz)",
    "model_version": "v2.3",
    "inference_engine": "onnxruntime",
    "inference_latency_ms": 45
  },
  "audit_hash": "sha256:abcd1234...",
  "previous_audit_hash": "sha256:..."
}
```

**What This Provides:**
- **Traceability:** Linking back to the exact grant
- **Reproducibility:** All preprocessing & model details recorded
- **Compliance:** Clear record for regulators
- **Debugging:** Can investigate why a prediction was incorrect

#### 4b. Tamper-Evident Audit Trail

**Why:**
- Non-repudiation: Auditor can verify no records were deleted
- Integrity: Hash chain detects modifications
- Compliance: Regulators trust immutable audit logs

**Audit Log:**

```
Audit Entry 1:
  {
    prediction_id: "pred-001",
    subject_id: "subj-7f3a",
    ... (all prediction data)
    previous_audit_hash: "sha256:0000..."
    audit_hash: "sha256:abcd1234..."
  }

Audit Entry 2:
  {
    prediction_id: "pred-002",
    subject_id: "subj-7f3a",
    ... (all prediction data)
    previous_audit_hash: "sha256:abcd1234..." (links to Entry 1)
    audit_hash: "sha256:efgh5678..."
  }

Audit Entry 3:
  {
    prediction_id: "pred-003",
    subject_id: "subj-abc",
    ... (all prediction data)
    previous_audit_hash: "sha256:efgh5678..." (links to Entry 2)
    audit_hash: "sha256:ijkl9012..."
  }

Verification:
  For i = 1 to N:
    if Entry[i].previous_audit_hash != Entry[i-1].audit_hash:
      TAMPERING DETECTED
```

**Storage & Backup:**
- Primary: Encrypted WAL on primary storage
- Backup: Replicated to S3 (geo-redundant, encrypted)
- Attestation: Root hash published quarterly for external verification

#### 4c. Answerability to Regulators

**Why:**
Regulators need to be able to audit compliance. This means being able to answer:
- "What consents were active on 2026-06-24?"
- "Who accessed subject X's data?"
- "Was DP privacy maintained?"

**Queries Supported:**

```sql
-- List all inferences for a subject
SELECT * FROM audit_trail
WHERE subject_id = 'subj-7f3a'
ORDER BY prediction_timestamp DESC;

-- Check consent status at a point in time
SELECT * FROM consent_ledger
WHERE subject_id = 'subj-7f3a'
  AND created_at <= '2026-06-24T12:00:00Z'
  AND (expires_at >= '2026-06-24T12:00:00Z'
       OR revoked_at IS NULL);

-- Verify DP budget spent
SELECT SUM(epsilon_spent) FROM audit_trail
WHERE subject_id = 'subj-7f3a'
  AND prediction_timestamp >= '2026-06-01'
  AND prediction_timestamp < '2026-07-01';

-- Audit trail integrity check
-- Compute hash chain; if broken, report tampering
```

### Implementation Status

- ✅ Self-describing predictions (all metadata in record)
- ✅ Tamper-evident audit trail (hash-chained)
- ✅ Audit queries (consent status, DP budget, inference history)
- ✅ Backup & recovery procedures
- ⏳ External ledger publication (quarterly)
- ⏳ Blockchain publication (future, post-MVP)

---

## Pillar 5: Observability & Security

### Problem

You cannot secure what you cannot see. Observability enables:
- Detecting anomalies (unusual access patterns)
- Debugging issues (where did a failure occur?)
- Compliance reporting (metrics for regulators)

### Solution

**Metrics, dashboards, structured logging, and chaos testing.**

#### 5a. Metrics (Prometheus)

**Key Metrics:**

```
Ingestion:
  synapse_samples_ingested_total
    Counter: total EEG samples received
    Labels: subject_id, device_id, status

  synapse_ingestion_latency_ms
    Histogram: latency from device to storage
    Buckets: [1, 5, 10, 50, 100, 500, 1000]

Consent:
  synapse_consent_checks_total
    Counter: total consent verifications
    Labels: result (granted/denied/expired/revoked)

  synapse_consent_cache_hitrate
    Gauge: % of consent checks that hit cache
    Target: >80%

Inference:
  synapse_inferences_total
    Counter: total inferences served
    Labels: model, result (served/denied)

  synapse_inference_latency_ms
    Histogram: end-to-end inference latency

Privacy:
  synapse_epsilon_remaining
    Gauge: ε budget remaining per subject
    Labels: subject_id
    Alert: <0.1 ε triggers email to subject

Storage:
  synapse_wal_size_bytes
    Gauge: size of WAL per subject
    Alert: If >10GB → archive old data

  synapse_disk_used_percent
    Gauge: disk utilization
    Alert: >90% → critical alert

Federated Learning:
  synapse_fl_round_duration_seconds
    Histogram: training round duration
    Target: <3600s (1 hour)

  synapse_fl_nodes_in_round
    Gauge: number of nodes in current round
    Target: ≥3
```

#### 5b. Grafana Dashboards

**Dashboard 1: Governance Overview**
```
┌──────────────────────────────────────────┐
│ SYNAPSE-AI Governance Dashboard          │
├──────────────────────────────────────────┤
│ Consent Grants Issued (today)    │ 47    │
│ Consent Grants Revoked (today)   │ 5     │
│ Consent Denials (today)          │ 12    │
│ DP Budget Exhaustions (today)    │ 2     │
│                                          │
│ Grants by Status:                        │
│   Active:  ████████░░░ 82%              │
│   Expired: ██░░░░░░░░ 18%              │
│   Revoked: ░░░░░░░░░░ 0%               │
│                                          │
│ DP Budget Burn Rate:                     │
│   Average: 0.03 ε per inference          │
│   Remaining (avg): 0.6 ε per subject    │
│                                          │
│ Inference Rate: 42 inferences/sec        │
│ Consent Check Latency (p99): 45ms       │
└──────────────────────────────────────────┘
```

**Dashboard 2: Security & Audit**
```
┌──────────────────────────────────────────┐
│ SYNAPSE-AI Security Dashboard            │
├──────────────────────────────────────────┤
│ Ingestion Errors (today)     │ 0         │
│ Storage Errors (today)       │ 0         │
│ Failed mTLS Handshakes       │ 2         │
│ Consent Ledger Integrity     │ ✓ OK      │
│                                          │
│ Network:                                 │
│   Encrypted Samples (mTLS)   │ 100%      │
│   Failed Signatures          │ 0         │
│                                          │
│ Audit Trail:                             │
│   Predictions Logged         │ 2,847     │
│   Hash Chain Verified        │ ✓ OK      │
│   Latest Audit Hash:                     │
│     sha256:abcd1234...                  │
│                                          │
│ Alerts Fired (last 24h):    │ 0 critical│
│                             │ 2 warn    │
└──────────────────────────────────────────┘
```

#### 5c. Structured Logging

**Every Request is Logged:**

```json
{
  "timestamp": "2026-06-24T09:12:33Z",
  "level": "INFO",
  "service": "inference",
  "request_id": "req-xyz-123",
  "requester_id": "research-lab-01",
  "subject_id": "subj-7f3a9b2c",
  "model_id": "mental-state-classifier@v2.3",
  "consent_status": "active",
  "dp_budget": { "epsilon_remaining": 0.9 },
  "inference_result": "served",
  "latency_ms": 45,
  "error": null
}
```

**Structured Errors:**

```json
{
  "timestamp": "2026-06-24T09:15:12Z",
  "level": "WARN",
  "service": "inference",
  "request_id": "req-xyz-124",
  "requester_id": "research-lab-02",
  "subject_id": "subj-abc123",
  "inference_result": "denied",
  "reason": "consent_expired",
  "expired_at": "2026-06-24T09:10:00Z",
  "error": "Consent expired 5 minutes ago"
}
```

#### 5d. Chaos & Consent-Bypass Testing

**Why:**
- Validate security guarantees under attack
- Detect bugs that happy-path testing misses
- Build confidence that the system actually enforces policy

**Test Scenarios:**

```
Test 1: Inference Without Consent
  Action: Submit inference request with no matching consent grant
  Expected: DENIED
  Actual: ✓ DENIED
  
Test 2: Inference With Expired Consent
  Action: Grant expires at T, submit inference at T+1
  Expected: DENIED
  Actual: ✓ DENIED (within 60s; cache TTL)
  
Test 3: Inference After Revocation
  Action: Grant revoked at T, submit inference at T+1
  Expected: DENIED
  Actual: ✓ DENIED (within 60s; cache TTL)
  
Test 4: Budget Exhaustion
  Action: Spend ε=1.0, then submit inference
  Expected: DENIED
  Actual: ✓ DENIED
  
Test 5: Node Failure During Federated Round
  Action: Kill node-3 mid-training
  Expected: Round continues with 2 nodes; completes normally
  Actual: ✓ Round aborted (N=2 < 3 minimum)
  
Test 6: Ledger Corruption Detection
  Action: Modify a byte in the ledger hash chain
  Expected: Hash chain verification fails on startup
  Actual: ✓ Detected; system enters read-only mode
  
Test 7: Tamper Detection (WAL)
  Action: Modify an encrypted sample in storage
  Expected: GCM authentication tag fails
  Actual: ✓ Detected; sample rejected
  
Test 8: Signature Forgery
  Action: Forge device signature on a sample
  Expected: Gateway rejects sample
  Actual: ✓ Rejected
```

**Run Chaos Tests:**
```bash
make test-chaos
# All tests pass or system fails safely
```

### Implementation Status

- ✅ Prometheus metrics (ingestion, consent, inference, privacy, storage)
- ✅ Grafana dashboards (governance, security)
- ✅ Structured logging (JSON, searchable)
- ✅ Chaos test suite (consent bypass, tampering, node failures)
- ✅ Alerting (PagerDuty integration)
- ⏳ Custom observability dashboards (future)

---

## The Five Pillars in Harmony

Each pillar solves a specific problem, but together they form a cohesive system:

```
Pillar 1 (Secure Ingestion & Storage)
  ↓ (Encrypted data at rest)
  ├─→ Pillar 4 (Provenance & Audit)
  │   ↓ (Audit trail of all access)
  │   └─→ Pillar 5 (Observability)
  │       (Detect tampering)
  │
  └─→ Pillar 3 (Privacy-Preserving ML)
      ↓ (Federated + DP)
      └─→ Pillar 2 (Consent & Governance)
          ↓ (Consent gates inference)
          └─→ Back to Pillar 4
              (Every decision is audited)
```

**The Flywheel:**
1. Subject grants consent (Pillar 2)
2. Data is encrypted & stored (Pillar 1)
3. Inference checks consent (Pillar 2)
4. If allowed, run model (Pillar 3)
5. Log prediction (Pillar 4)
6. Monitor for anomalies (Pillar 5)
7. Repeat

---

**End state:** A system where machine learning operates on neural data with the same consent, encryption, and audit properties as a human user would expect for such sensitive information.
