# ARCHITECTURE.md — SYNAPSE-AI

**System Architecture Overview**

**Last Updated:** June 24, 2026  
**Status:** In Development

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architectural Principles](#architectural-principles)
3. [Component Diagram](#component-diagram)
4. [Data Flow](#data-flow)
5. [Service Interactions](#service-interactions)
6. [Scalability & Resilience](#scalability--resilience)
7. [Deployment Models](#deployment-models)

---

## System Overview

SYNAPSE-AI is a **consent-governed neural data platform** where machine learning is treated as a governed consumer, not a privileged actor. The architecture inverts the typical "data store → bolt on access control → add a model" approach.

**Core Principle:** *The governance and consent layer IS the system. Everything else (storage, inference, federated learning) are gated consumers that must obey the same rules as human users.*

### What Makes It Different

| Aspect | Traditional ML | SYNAPSE-AI |
| --- | --- | --- |
| **Data model** | Central store (all data in one place) | Distributed (data stays at the edge) |
| **Access control** | Bolted on after storage | First-class, enforced on every request |
| **Model permissions** | Privileged (can read whenever) | Governed (must ask and wait for verification) |
| **Revocation** | Eventually consistent | Synchronous and immediate |
| **Audit trail** | Optional, often incomplete | Mandatory, tamper-evident, comprehensive |
| **Privacy** | Best-effort (or none) | Formal guarantees (differential privacy) |

---

## Architectural Principles

### 1. **Consent is First-Class**

Consent is not a form subjects sign once. It's a runtime object that gates every inference and training operation.

```
Every request → Consent check → Pass/Fail decision → Request proceeds/denied
```

Revocation is immediate; no eventual consistency. A subject revokes at T=0, inferences at T>0 are denied.

### 2. **Encryption at the Edge**

Neural samples are encrypted before they leave the device. The platform never sees plaintext data.

```
Device: Sample → Sign → Encrypt → Transmit (encrypted)
Gateway: Receive (encrypted) → Verify signature → Store (encrypted)
```

### 3. **Immutability & Tamper-Evidence**

All writes are append-only. Nothing can be modified in-place. Hash chains detect tampering.

```
Entry 1 → hash1
Entry 2 → hash(Entry 2 + hash1)
Entry 3 → hash(Entry 3 + hash2)
...
Chain break → Tampering detected
```

### 4. **Federated Learning (Data Never Leaves)**

Models train locally on each node. Only differentially-private gradients are aggregated. Raw data stays put.

```
Node 1: Raw data (encrypted, stays on-node)
         ↓
       Train model locally
         ↓
       Compute gradients
         ↓
       Add DP noise
         ↓
       Send (noisy gradients only)
         ↓
         Server: Aggregate from all nodes
```

### 5. **Formal Privacy Budgets**

Privacy is not a promise; it's a quota. DP budgets are tracked and enforced. Once spent, no more inferences.

```
Subject epsilon budget: 1.0
After 10 inferences: 0.0 remaining
Status: BUDGET_EXHAUSTED
```

### 6. **Synchronous Verification**

Every request is checked *before* processing. No cached "probably yes" decisions.

```
Inference request → Consent check (live) → DP budget check (live) → Serve/Deny
```

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SYNAPSE-AI PLATFORM                          │
└─────────────────────────────────────────────────────────────────────┘

                        ┌──────────────────────┐
                        │  SUBJECT / REQUESTER │ (external)
                        │  (via mTLS identity) │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
            ┌───────▼────┐   ┌────▼──────┐   ┌──▼────────┐
            │   INGESTION│   │  INFERENCE│   │  AUDIT    │
            │   GATEWAY  │   │  API      │   │  QUERY    │
            │  (mTLS)    │   │  (mTLS)   │   │  (mTLS)   │
            └───────┬────┘   └────┬──────┘   └──┬────────┘
                    │              │             │
            ┌───────┼──────────────┼─────────────┼─────┐
            │       │              │             │     │
    ┌───────▼────┐  │  ┌──────────▼──────┐    │     │
    │  CONSENT   │  │  │   INFERENCE     │    │     │
    │  ENGINE    │  │  │   SERVICE       │    │     │
    │ (ledger)   │  │  │                 │    │     │
    └──────┬─────┘  │  └────────┬────────┘    │     │
           │        │           │             │     │
    ┌──────▼────────▼───────────▼──────┐     │     │
    │                                  │     │     │
    │        STORAGE SERVICE           │     │     │
    │  (Append-only WAL + Index)      │     │     │
    │                                  │     │     │
    │  ┌─────────────────────────────┐ │     │     │
    │  │ Subject 1 (encrypted WAL)   │ │     │     │
    │  └─────────────────────────────┘ │     │     │
    │  ┌─────────────────────────────┐ │     │     │
    │  │ Subject 2 (encrypted WAL)   │ │     │     │
    │  └─────────────────────────────┘ │     │     │
    │  ┌─────────────────────────────┐ │     │     │
    │  │ Consent Ledger (encrypted)  │ │     │     │
    │  └─────────────────────────────┘ │     │     │
    │  ┌─────────────────────────────┐ │     │     │
    │  │ Audit Trail (encrypted)     │ │     │     │
    │  └─────────────────────────────┘ │     │     │
    └──────────────────────────────────┘     │     │
           │                                  │     │
    ┌──────▼────────────────────────┐        │     │
    │                               │        │     │
    │   FEDERATED ORCHESTRATOR      │        │     │
    │   (Model distribution + Agg)  │        │     │
    │                               │        │     │
    └──────────────────────────────┘        │     │
           │                                  │     │
    ┌──────▼─────────────────────────────────┘     │
    │                                              │
    ├─ Node 1: Local training                     │
    ├─ Node 2: Local training                     │
    ├─ Node 3: Local training                     │
    └─ Aggregator: DP gradient aggregation        │
           │                                       │
    ┌──────▼───────────────────────────────────────┘
    │
    │  KMS (Key Management Service)
    │  - Subject encryption keys
    │  - WAL encryption keys
    │  - Ledger signing keys
```

---

## Data Flow

### 1. Ingestion Path (EEG Sample → Storage)

```
┌─────────────────────────────────────────────────────────────────┐
│ Subject's Edge Device (e.g., EEG Headset)                       │
│                                                                  │
│  EEG Sample (raw, plaintext on device only)                    │
│         ↓                                                        │
│  Sign with device private key (ECDSA)                          │
│         ↓                                                        │
│  Encrypt with subject's data key (AES-256-GCM)                 │
│         ↓                                                        │
│  mTLS handshake (authenticate device cert)                     │
│         ↓                                                        │
│  Send: { encrypted_payload, nonce, auth_tag, device_signature }│
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼ (over encrypted mTLS channel)
┌─────────────────────────────────────────────────────────────────┐
│ Gateway (Ingestion Service)                                      │
│                                                                  │
│  Receive encrypted sample                                       │
│         ↓                                                        │
│  Verify device mTLS cert (certificate chain, not revoked)      │
│         ↓                                                        │
│  Verify device signature (ECDSA)                               │
│         ↓                                                        │
│  Reject if signature invalid (tampering)                        │
│         ↓                                                        │
│  Extract subject_id from device cert                            │
│         ↓                                                        │
│  Reject if subject not enrolled                                │
│         ↓                                                        │
│  Forward to Storage Service (still encrypted)                   │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Storage Service (Write-Ahead Log)                                │
│                                                                  │
│  Receive encrypted sample + metadata                            │
│         ↓                                                        │
│  Append to subject's WAL (on disk)                              │
│         ↓                                                        │
│  fsync() to ensure durability                                   │
│         ↓                                                        │
│  Update index (subject_id → offset in WAL)                      │
│         ↓                                                        │
│  Send ACK to gateway                                            │
│         ↓                                                        │
│  Gateway sends ACK to device                                    │
└─────────────────────────────────────────────────────────────────┘

Result: Encrypted sample is durable, tamper-evident
```

### 2. Inference Path (Request → Prediction)

```
┌─────────────────────────────────────────────────────────────────┐
│ Requester (Research Lab)                                         │
│                                                                  │
│  InferenceRequest {                                             │
│    subject_id: "subj-7f3a"                                      │
│    model: "mental-state-classifier@v2.3"                        │
│    purpose: "attention/fatigue research"                        │
│  }                                                              │
│         ↓                                                        │
│  mTLS handshake (authenticate requester cert)                   │
│         ↓                                                        │
│  Send request (encrypted channel)                               │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Gateway (Inference Service)                                      │
│                                                                  │
│  Receive request                                                │
│         ↓                                                        │
│  Extract requester identity from mTLS cert                      │
│         ↓                                                        │
│  Verify: subject exists and is enrolled                         │
│         ↓                                                        │
│  Query Consent Engine:                                          │
│    "Is there active consent for (subj-7f3a, model-v2.3,        │
│     attention/fatigue research)?"                               │
└─────────────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
     ┌──────▼──────┐            ┌──────▼──────┐
     │  CONSENT?   │            │   CONSENT   │
     │   NO        │            │   ENGINE    │
     │  (denied)   │            │ (Ledger)    │
     └──────┬──────┘            └──────┬──────┘
            │                          │
            │                   ┌──────▼────────┐
            │                   │ Check grant   │
            │                   │ (O(log N))    │
            │                   │ lookup + cache│
            │                   └──────┬────────┘
            │                          │
            │              ┌───────────┴──────────────┐
            │              │                          │
        ┌───▼──────┐   ┌───▼──────┐   ┌────────────┐
        │ DENIED   │   │ ACTIVE   │   │ EXPIRED /  │
        │ (no      │   │ (proceed)│   │ REVOKED    │
        │ grant)   │   │          │   │ (denied)   │
        └───┬──────┘   └───┬──────┘   └────────┬───┘
            │              │                   │
    ┌───────┴──────────────┼───────────────────┴─────┐
    │                      │                         │
    │              ┌──────▼──────────┐               │
    │              │ Check DP Budget │               │
    │              │ epsilon_remain? │               │
    │              └──────┬──────────┘               │
    │                     │                         │
    │            ┌────────┴──────────┐              │
    │            │                   │              │
    │        ┌───▼────┐         ┌────▼────┐         │
    │        │ DENY   │         │ ALLOW   │         │
    │        │ Budget │         │ Proceed │         │
    │        │exhausted         │         │         │
    │        └───┬────┘         └────┬────┘         │
    │            │                   │              │
    │ ┌──────────┴───────────────────┴──────────┐   │
    │ │                                         │   │
    │ │  If Denied: Return error               │   │
    │ │  If Allowed: Proceed to Inference      │   │
    └─┼─────────────────────────────────────────┼───┘
      │                                         │
      └─────────────┬──────────────────────────┘
                    │
            ┌───────▼──────────┐
            │ Fetch Subject    │
            │ Neural Data      │
            │ (from Storage)   │
            └───────┬──────────┘
                    │
            ┌───────▼──────────┐
            │ Decrypt Data     │
            │ (subject key)    │
            └───────┬──────────┘
                    │
            ┌───────▼──────────┐
            │ Preprocess EEG   │
            │ (bandpass, downsample)
            └───────┬──────────┘
                    │
            ┌───────▼──────────┐
            │ Run Model        │
            │ (inference)      │
            └───────┬──────────┘
                    │
            ┌───────▼──────────┐
            │ Add DP Noise     │
            │ (Laplace mech)   │
            └───────┬──────────┘
                    │
            ┌───────▼──────────┐
            │ Create Provenance│
            │ Record           │
            │ (prediction +    │
            │  model version + │
            │  consent grant + │
            │  DP ε spent)     │
            └───────┬──────────┘
                    │
            ┌───────▼──────────┐
            │ Log to Audit     │
            │ Trail (append-   │
            │ only, encrypted) │
            └───────┬──────────┘
                    │
            ┌───────▼──────────┐
            │ Return Result    │
            │ + Provenance     │
            └───────┬──────────┘
                    │
                    ▼
            ┌──────────────────┐
            │ Requester        │
            │ receives result  │
            └──────────────────┘

Result: Prediction served with full governance trail
```

### 3. Federated Learning Path (Training → Aggregation)

```
┌──────────────────────────────────────────────────────────────────┐
│ FL Orchestrator (Python Service)                                  │
│                                                                   │
│  Federated Round Initiated                                        │
│  - Select nodes (N ≥ 3)                                          │
│  - Create model snapshot                                          │
│  - Broadcast to nodes: "Start training"                          │
└──────────────────────────────────────────────────────────────────┘
        │
        ├─────────────────────────┬────────────────────────┐
        │                         │                        │
        ▼                         ▼                        ▼
  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
  │ Node 1       │         │ Node 2       │         │ Node 3       │
  │ (Subject A's │         │ (Subject B's │         │ (Subject C's │
  │  data)       │         │  data)       │         │  data)       │
  │              │         │              │         │              │
  │ ┌──────────┐ │         │ ┌──────────┐ │         │ ┌──────────┐ │
  │ │Raw data  │ │         │ │Raw data  │ │         │ │Raw data  │ │
  │ │(encrypted)         │ │(encrypted)         │ │(encrypted)
  │ └────┬─────┘ │         │ └────┬─────┘ │         │ └────┬─────┘ │
  │      │       │         │      │       │         │      │       │
  │ ┌────▼─────┐ │         │ ┌────▼─────┐ │         │ ┌────▼─────┐ │
  │ │Train for │ │         │ │Train for │ │         │ │Train for │ │
  │ │5 epochs  │ │         │ │5 epochs  │ │         │ │5 epochs  │ │
  │ │(locally) │ │         │ │(locally) │ │         │ │(locally) │ │
  │ └────┬─────┘ │         │ └────┬─────┘ │         │ └────┬─────┘ │
  │      │       │         │      │       │         │      │       │
  │ ┌────▼─────────────┐   │ ┌────▼─────────────┐   │ ┌────▼─────────────┐
  │ │Compute gradients │   │ │Compute gradients │   │ │Compute gradients │
  │ │& losses          │   │ │& losses          │   │ │& losses          │
  │ └────┬─────────────┘   │ └────┬─────────────┘   │ └────┬─────────────┘
  │      │       │         │      │       │         │      │       │
  │ ┌────▼─────┐ │         │ ┌────▼─────┐ │         │ ┌────▼─────┐ │
  │ │Clip grad │ │         │ │Clip grad │ │         │ │Clip grad │ │
  │ │per-sample│ │         │ │per-sample│ │         │ │per-sample│ │
  │ │(L2 norm) │ │         │ │(L2 norm) │ │         │ │(L2 norm) │ │
  │ └────┬─────┘ │         │ └────┬─────┘ │         │ └────┬─────┘ │
  │      │       │         │      │       │         │      │       │
  │ ┌────▼─────┐ │         │ ┌────▼─────┐ │         │ ┌────▼─────┐ │
  │ │Add DP    │ │         │ │Add DP    │ │         │ │Add DP    │ │
  │ │noise    │ │         │ │noise    │ │         │ │noise    │ │
  │ │(Laplace)│ │         │ │(Laplace)│ │         │ │(Laplace)│ │
  │ └────┬─────┘ │         │ └────┬─────┘ │         │ └────┬─────┘ │
  │      │       │         │      │       │         │      │       │
  │ ┌────▼──────────┐      │ ┌────▼──────────┐      │ ┌────▼──────────┐
  │ │Send to        │      │ │Send to        │      │ │Send to        │
  │ │orchestrator   │      │ │orchestrator   │      │ │orchestrator   │
  │ │(encrypted)    │      │ │(encrypted)    │      │ │(encrypted)    │
  │ └────┬──────────┘      │ └────┬──────────┘      │ └────┬──────────┘
  │      │       │         │      │       │         │      │       │
  └──────┼───────┘         └──────┼───────┘         └──────┼───────┘
         │                        │                        │
         └────────────────┬───────┴────────────────┬───────┘
                          │                        │
                   ┌──────▼────────────────────────▼───┐
                   │ FL Orchestrator                    │
                   │ (Aggregator)                       │
                   │                                    │
                   │ Collect gradients from nodes      │
                   │ ┌──────────────────────────────┐  │
                   │ │ Gradient from Node 1 (DP)    │  │
                   │ │ Gradient from Node 2 (DP)    │  │
                   │ │ Gradient from Node 3 (DP)    │  │
                   │ └──────────────────────────────┘  │
                   │              ↓                    │
                   │ Aggregate: avg(grad1, grad2, 3)  │
                   │              ↓                    │
                   │ Update model weights              │
                   │              ↓                    │
                   │ Save new model version (v2.4)    │
                   │              ↓                    │
                   │ Deploy to inference service       │
                   └──────────────────────────────────┘

Result: Model trained without centralizing data + DP guarantees
```

---

## Service Interactions

### Gateway ↔ Consent Engine

```
Gateway: "Can subject-7f3a use model-v2.3 for 'research'?"
    │
    ▼
Consent Engine:
1. Look up grant in ledger (cache-backed)
2. Check expiration: expires_at > now?
3. Check revocation: any revocation after grant?
4. Return: { status: "ACTIVE" | "DENIED" | "EXPIRED" | "REVOKED" }

Gateway: Proceed or deny inference
```

### Gateway ↔ Storage Service

```
Ingestion:
Gateway: "Store encrypted sample from subject-7f3a"
Storage: Write to WAL, fsync, return ACK

Inference:
Gateway: "Fetch encrypted samples for subject-7f3a"
Storage: Read from WAL index, return encrypted data
Gateway: Decrypt (has key), preprocess, run model
```

### Inference Service ↔ Audit Service

```
Inference Service: "Log this prediction"
    {
      "prediction": {"attention": 0.71, ...},
      "subject_id": "subject-7f3a",
      "model": "mental-state-classifier@v2.3",
      "consent_grant_id": "grant-abc",
      "epsilon_spent": 0.1,
      ...
    }

Audit Service:
1. Append to audit log (encrypted)
2. Compute hash(previous_audit_record + this_record)
3. Return audit_hash (commitment)

Inference Service: Include audit_hash in response
```

### Orchestrator ↔ Nodes (Federated Learning)

```
Orchestrator: "Round started. Download model v2.3, train for 5 epochs"
    │
    ├─→ Node 1: Download model
    ├─→ Node 2: Download model
    └─→ Node 3: Download model

Nodes: Train locally (data stays on-node)

Orchestrator: "Send gradients"
    ↑
    ├─ Node 1: Send DP gradients (encrypted)
    ├─ Node 2: Send DP gradients (encrypted)
    └─ Node 3: Send DP gradients (encrypted)

Orchestrator:
1. Aggregate (average)
2. Update model weights
3. Increment version (v2.4)
4. Broadcast new model
```

---

## Scalability & Resilience

### Scalability Dimensions

| Dimension | Strategy | Limit |
| --- | --- | --- |
| **Subjects** | Shard storage by subject_id | 1M+ subjects |
| **Ingestion rate** | Horizontal scale gateway instances | 10K+ samples/sec |
| **Inference rate** | Horizontal scale inference services | 1K+ inferences/sec |
| **Consent checks** | Cache + read replicas | 10K+ checks/sec |
| **Federated nodes** | Node sharding (tree aggregation) | 1000+ nodes |

### Resilience Patterns

**Consent Service Down:**
- Fallback to 60-second cached consent decision
- Read replicas for ledger queries
- Return error (fail-safe) if cache miss

**Storage Node Down:**
- Replication (RAID or S3 backup)
- WAL durability (fsync before ACK)
- Geo-redundancy for critical ledgers

**Inference Service Crash:**
- Predictions not returned, but still logged (fire-and-forget to audit)
- Requester times out; can retry
- Ledger unaffected

**Federated Node Failure:**
- Timeout after T seconds (e.g., 3600s)
- Aggregate from remaining nodes if N-1 ≥ 3
- Abort round if insufficient nodes

---

## Deployment Models

### Local Development

```
Single machine, all services running:
- Gateway on :8443
- Storage on :9090
- Inference on :8444
- FL Orchestrator (Python) on :5000
```

### Docker Compose (Small Cluster)

```
Single Docker host, multiple containers:
- synapse-gateway (Go)
- synapse-storage (Rust)
- synapse-inference (Go)
- synapse-fl-orchestrator (Python)
- postgres (for ledger)
```

### Kubernetes (Production)

```
Distributed across 3+ K8s nodes:

Namespace: synapse-ai

Deployments:
- synapse-gateway (replicas: 3)
- synapse-storage (replicas: 2)
- synapse-inference (replicas: 3)
- synapse-fl-orchestrator (replicas: 1)

StatefulSets:
- postgres (postgres-0, replicas: 1)

PersistentVolumes:
- storage: 100GB
- ledger: 10GB
- audit: 50GB

Services:
- synapse-gateway-svc (LoadBalancer, external)
- synapse-storage-svc (ClusterIP, internal)
- synapse-inference-svc (ClusterIP, internal)

Monitoring:
- prometheus (metrics scraping)
- grafana (dashboards)
- loki (log aggregation)
```

---

## Security Architecture

### Threat Prevention

```
┌────────────────────────────────────────┐
│ Subject's Device                       │
│ ┌──────────────────────────────────┐   │
│ │ Sample (plaintext only here)     │   │
│ │ ↓                                │   │
│ │ Sign (ECDSA) + Encrypt (AES-256)│   │
│ │ ↓                                │   │
│ │ Never plaintext off-device       │   │
│ └──────────────────────────────────┘   │
└────────────────────────────────────────┘
        │ mTLS encrypted channel
        ▼
┌────────────────────────────────────────┐
│ Gateway (Authentication & Routing)     │
│ - Verify device mTLS cert             │
│ - Verify device signature              │
│ - Verify subject enrolled              │
│ - Route to appropriate service         │
└────────────────────────────────────────┘
        │
        ├─→ Ingestion: Encrypted → Storage
        │
        ├─→ Inference:
        │   1. Consent check (synchronous)
        │   2. DP budget check
        │   3. Decrypt data (only if allowed)
        │   4. Run model
        │   5. Log to audit (tamper-evident)
        │
        └─→ Other: Audit queries, etc.
```

---

## Operational Flows

### Enrollment

```
1. Subject creates account (web UI)
2. Subject downloads edge app
3. App requests enrollment token
4. Subject enters token in app
5. App generates device CSR
6. Platform CA signs cert
7. App stores cert in device secure storage
8. App is ready to collect EEG
```

### Consent Grant

```
1. Subject navigates to "Grant Consent"
2. Selects model and purpose
3. Confirms with 2FA
4. Grant appended to consent ledger
5. Subject receives notification
6. Grant is immediately usable for inference
```

### Inference

```
1. Requester sends request (mTLS authenticated)
2. Gateway verifies consent (ledger lookup + cache)
3. If allowed:
   a. Fetch encrypted data
   b. Decrypt
   c. Preprocess
   d. Run model
   e. Add DP noise
   f. Log to audit
   g. Return result
4. If denied: Return error
```

### Revocation

```
1. Subject revokes consent (web UI)
2. Revocation appended to ledger
3. Consent cache invalidated (or expires within 60s)
4. Future inferences denied immediately
5. Subject receives confirmation
```

---

**This architecture treats machine learning as a governed consumer, not a privileged actor.**
