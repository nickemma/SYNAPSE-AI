# SYNAPSE-AI — Consent-Governed Neural Data & Privacy-Preserving ML

![Status](https://img.shields.io/badge/status-In%20development-orange)
![Go Version](https://img.shields.io/badge/go-1.25-blue)
![Rust Version](https://img.shields.io/badge/rust-1.87-orange)
![Python Version](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-APACHE-green)
[![CI](https://github.com/nickemma/meridian/workflows/CI/badge.svg)](https://github.com/nickemma/synapse-ai/actions)


**A platform for the most sensitive data humans generate — neural signals — where AI is a *privileged consumer that must obey the same consent, encryption, and audit rules as any human user.***

*Encrypted at the edge. Stored append-only. Analysed only under active consent and differential privacy. Models trained via federated learning — the model travels to the data, never the reverse. Every prediction carries its own provenance.*

[What is SYNAPSE-AI?](#what-is-synapse-ai) • [Architecture](#architecture) • [The Pillars](#the-five-pillars) • [Quick Start](#quick-start) • [Threat Model](docs/THREAT_MODEL.md) • [Roadmap](#roadmap)

---

## What is SYNAPSE-AI?

Most "AI + sensitive data" systems get the architecture backwards. They build a data store, attach a model, and bolt access control onto the side. The model becomes a privileged actor that sits *outside* the governance system, reaching into the data whenever it likes.

SYNAPSE-AI inverts that. Here, **the consent and governance layer is the system**, and machine learning is just another consumer that has to ask permission like everyone else. An inference request is subject to the same checks as a human reading a record: who are you, what subject's data do you want, do you have active consent for this purpose, is your privacy budget intact, and will this decision be recorded? If any check fails, the model never sees the data.

The reason this matters is the data itself. Neural signals are not like a shopping cart or a session token — they are the closest thing to a direct readout of a person. You cannot rotate a brain. So the system is built from the threat model up, and the central design rule is non-negotiable: **the platform treats AI as a privileged consumer of data that must obey the same consent, encryption, auditing, and governance rules as any human user.**

The real innovation is not that a model runs on EEG data. It is that the model is governed *identically* to a person — and that the hardest privacy problems (training without centralising data, bounding what a model can leak, proving after the fact what a prediction was allowed to do) are solved in the architecture rather than promised in a policy document.

**The real question this system answers:** *How can machine learning operate on highly sensitive neural data while preserving ownership, consent, auditability, and privacy?*

---

## What Each Layer Proves

| Layer | What It Demonstrates |
| --- | --- |
| Edge encryption & signing | Crypto at the source — neural samples are never plaintext once they leave the device |
| Append-only encrypted storage | Storage internals, encryption at rest, tamper-evidence on the most sensitive data class |
| Consent & governance engine | The core thesis — AI is a *gated* consumer, not a privileged one; deny-by-default for models and humans alike |
| Federated learning | Distributed ML done right — bring the model to the data, never the data to the model |
| Differential privacy | Formal, budgeted privacy guarantees — not just access control, but bounded leakage |
| Prediction provenance & audit | AI governance and regulatory-grade traceability — every prediction is self-describing |
| mTLS + identity from the edge up | Zero-trust networking before a single byte of signal is accepted |
| Chaos + consent-bypass testing | Correctness under adversarial conditions — the compelling demo, not the happy path |

---

## Architecture

The data path is a one-way gauntlet. Nothing reaches a model without clearing every gate before it.

```
        EEG / Neural Signal (edge device)
                    │
                    ▼
        Encrypted Ingestion          ── signed + encrypted at the edge, mTLS to the gateway
                    │
                    ▼
        Secure Storage               ── append-only, encrypted-at-rest log
                    │
                    ▼
        Consent Verification         ── active grant required for (subject, model, purpose)
                    │
                    ▼
        Privacy Layer                ── differential-privacy budget check + noise injection
                    │
                    ▼
        ML Inference                 ── model runs; cannot reach data without the gates above
                    │
                    ▼
        Result + Provenance Record   ── prediction stored with model, consent, requester, timestamp
```

Federated training runs *beside* this path, not through it: the model is shipped to each node, trains locally on data that never moves, and only differentially-private gradient updates return to be aggregated.

---

## The Five Pillars

### 1. Secure Ingestion & Storage — `ingest/` + `storage/`

The foundation: neural data is never plaintext once it leaves the device.

- **Edge signing & encryption** — every sample is signed with the device identity and encrypted before transmission; the gateway authenticates devices over mTLS and rejects anything unsigned
- **Append-only encrypted log** — samples land in a tamper-evident, AES-256-GCM-encrypted log; there is no in-place mutation of neural data, ever
- **Per-subject key isolation** — each subject's stream is encrypted under keys scoped to that subject, so a single key compromise cannot expose the corpus
- **Schema-validated ingestion** — malformed or out-of-band samples are rejected at the gateway, not after storage

### 2. Consent & Governance Engine — `consent/` *(the heart of the system)*

This is where SYNAPSE-AI differs from every "model on a dataset" project. Consent is a first-class, enforced, revocable object — and it gates models exactly as it gates people.

- **Structured, scoped grants** — a grant authorises a *specific model*, for a *specific purpose*, for a *bounded time* (e.g. `model X` / `research purpose Y` / `30 days`)
- **Verified before inference runs** — no model touches a subject's data without an active matching grant; the check is synchronous and on the request path
- **Revocation is immediate and honoured** — a subject can revoke at any time; in-flight and future inference for that grant stops
- **Deny-by-default** — a model with no matching consent has no access, identical to a human with no policy
- **Hash-chained consent ledger** — every grant, renewal, and revocation is appended to a tamper-evident log; you can prove what was permitted at any point in time

### 3. Privacy-Preserving ML — `ml/`

Useful machine learning, without surrendering ownership or centralising the data.

- **Federated learning** — models train locally on each node; only encrypted, differentially-private gradient updates leave the node. The raw neural data never moves. *Bring the model to the data.*
- **Differential privacy** — a per-subject privacy budget (ε) bounds how much any single individual can influence a model or be inferred from its outputs; budget is tracked and enforced, and exhausted budgets deny further use
- **Defensible, non-medical tasks** — mental-state classification on public EEG datasets (attention, fatigue, stress, cognitive workload) — achievable and clearly scoped, never diagnostic
- **Secure inference** — inference is itself a consent-gated, budgeted, audited operation, not a free-for-all over stored data

### 4. Provenance & Audit — `audit/`

Every prediction is self-describing. Months later, you can answer exactly what a model was allowed to do and why.

- **Self-describing predictions** — each result records its model version, training dataset, consent status, requesting entity, and timestamp
- **Tamper-evident audit trail** — records are hash-chained; the history cannot be silently rewritten
- **Answerable to regulators** — the kind of traceability AI governance frameworks increasingly require, built in rather than reconstructed after an incident
- **Consent-linked** — every prediction points back to the exact grant that authorised it

### 5. Observability & Security — `observability/`

- **Metrics** — inference rate per model, consent status distribution, differential-privacy budget remaining per subject, ingestion throughput, anomaly scores
- **Grafana dashboards** — consent grants vs. revocations, federated round progress, DP budget burn-down, gateway rejections
- **Structured logs** — every request with requester identity, subject, model, consent decision, and latency
- **Chaos & consent-bypass suite** — attempts to run inference without consent, with an expired grant, or after revocation, plus node failure during a federated round — all must fail safe

---

## Tech Stack

| Layer | Technology | Why |
| --- | --- | --- |
| **Edge acquisition & signing** | Rust | Real-time signal path, no GC pauses, cryptography at the source |
| **Storage engine** | Rust | Append-only encrypted log, WAL durability, no GC on the write path |
| **Gateway, consent engine, API** | Go | mTLS, gRPC, concurrent request handling, synchronous consent decisions |
| **Privacy-preserving ML** | Python | Federated orchestration, differential privacy, training on public EEG datasets |
| **Inter-node + client API** | gRPC + Protobuf | Typed, streaming, efficient model-update exchange |
| **Chaos + verification** | Python | Adversarial testing, consent-bypass attempts, federated-round fault injection |
| **Observability** | Prometheus + Grafana | Inference rates, consent status, DP budget, federated progress |

---

## Security as First Principles

- **AI is governed identically to a human** — same consent, encryption, audit, and deny-by-default rules; no privileged data path for models
- **Consent verified before every inference** — synchronous, on the request path; no active grant means no access
- **Differential-privacy budget enforced** — bounded leakage per subject; exhausted budgets deny further inference and training
- **The data never moves for training** — federated learning keeps raw neural signals on the node; only DP-protected updates leave
- **Encrypted at the edge and at rest** — AES-256-GCM; neural samples are never plaintext off-device or on disk
- **mTLS device & service identity** — every device and consumer authenticates with a certificate before any signal or request is processed
- **Revocation is real** — a revoked grant stops inference immediately; consent is not a one-time checkbox
- **Tamper-evident everywhere** — consent ledger and prediction provenance are hash-chained and end-to-end verifiable

---

## Quick Start

### Prerequisites

- Go 1.25
- Rust 1.87 (edge agent + storage engine)
- Python 3.12 (federated orchestrator + ML)
- Docker + docker-compose (multi-node federated cluster)

```bash
# Clone
git clone https://github.com/nickemma/synapse-ai.git
cd synapse-ai

# Start a local cluster (gateway + storage + 3 federated nodes)
make cluster-up

# Stream synthetic / sample EEG into encrypted ingestion
./bin/synapse ingest \
  --device device-01 \
  --source samples/eeg-public-sample.edf

# Grant scoped consent: one model, one purpose, time-bounded
./bin/synapse consent grant \
  --subject subject-7f3a \
  --model mental-state-classifier@v2.3 \
  --purpose "attention/fatigue research" \
  --scope inference \
  --ttl 30d

# Run inference — the system verifies consent + DP budget BEFORE the model sees data
./bin/synapse infer \
  --subject subject-7f3a \
  --model mental-state-classifier@v2.3 \
  --requester research-lab-01
# consent:        active        ✓
# privacy budget: ε=1.0 (ok)    ✓
# prediction:     attention=0.71   → recorded to audit

# Revoke consent — future inference for this grant stops immediately
./bin/synapse consent revoke --subject subject-7f3a --model mental-state-classifier@v2.3

# Inspect the provenance of a prediction
./bin/synapse audit show --prediction pred-9c2e

# Run one federated training round — model travels to data, only DP updates return
./bin/synapse fl round \
  --model mental-state-classifier \
  --nodes node-a,node-b,node-c \
  --dp-epsilon 1.0

# Run the consent-bypass chaos suite (must fail safe — destructive, isolated network)
make chaos-run
```

### A Consent Grant

```json
{
  "subject":    "subject-7f3a",
  "model":      "mental-state-classifier@v2.3",
  "purpose":    "attention/fatigue research",
  "scope":      ["inference"],
  "granted_at": "2026-06-24T09:00:00Z",
  "expires_at": "2026-07-24T09:00:00Z",
  "revocable":  true,
  "status":     "active"
}
```

### A Prediction Provenance Record

Every prediction is self-describing — this is what makes the audit trail meaningful:

```json
{
  "prediction":  { "attention": 0.71, "stress_level": 0.82 },
  "model":       "mental-state-classifier@v2.3",
  "dataset":     "public-eeg-2025-attention",
  "consent":     { "grant_id": "grant-41a8", "status": "active" },
  "requester":   "research-lab-01",
  "privacy":     { "epsilon_spent": 0.1, "epsilon_remaining": 0.9 },
  "timestamp":   "2026-06-24T09:12:33Z",
  "audit_hash":  "sha256:…"
}
```

### Inference Request (gRPC)

```protobuf
message InferenceRequest {
  string  subject_id   = 1;
  string  model        = 2;  // "name@version"
  string  requester    = 3;  // mTLS-verified consumer identity
  string  purpose      = 4;  // must match an active consent grant
}

message InferenceResponse {
  map<string, double> prediction        = 1;
  string              consent_status     = 2;  // "active" | "denied" | "expired" | "revoked"
  double              epsilon_spent      = 3;
  double              epsilon_remaining  = 4;
  string              audit_hash         = 5;  // provenance record commitment
  bool                served             = 6;  // false if any gate denied the request
}
```

### Environment Variables

```bash
SYNAPSE_GATEWAY_PORT=8443
SYNAPSE_STORAGE_DIR=/var/lib/synapse
SYNAPSE_WAL_ENCRYPTION_KEY=<32-byte-key>
SYNAPSE_MTLS_CA=/etc/synapse/ca.pem
SYNAPSE_CONSENT_DENY_BY_DEFAULT=true
SYNAPSE_DP_EPSILON_PER_SUBJECT=1.0       # privacy budget per subject
SYNAPSE_DP_DELTA=1e-5
SYNAPSE_FL_MIN_NODES=3                    # minimum nodes for a federated round
SYNAPSE_FL_AGGREGATION=secure-avg         # DP-protected gradient aggregation
SYNAPSE_AUDIT_HASH_CHAIN=true
SYNAPSE_CONSENT_LEDGER_HASH_CHAIN=true
```

---

## Engineering Deep Dive

Key system-design areas implemented in SYNAPSE-AI:

- Edge cryptography — per-sample signing and encryption, device identity via mTLS, plaintext never leaves the device
- Append-only encrypted storage — AES-256-GCM WAL, tamper-evidence, per-subject key isolation
- Consent engine — structured scoped grants, synchronous on-path verification, immediate revocation, deny-by-default for models *and* humans, hash-chained consent ledger
- Federated learning — bring-model-to-data training, DP-protected gradient aggregation, fault tolerance when a node drops mid-round
- Differential privacy — per-subject ε budget tracking and enforcement across both training and inference
- Prediction provenance — self-describing predictions linked to the authorising grant, hash-chained audit trail
- AI governance — the architectural treatment of a model as a governed consumer, not a privileged actor
- Chaos & consent-bypass testing — inference without/with expired/with revoked consent, node failure during federated rounds, all failing safe

**Blog (coming soon):** *"Treating AI Like a User: How SYNAPSE-AI Governs a Model the Same Way It Governs a Person."*

---

## Roadmap

- [ ] Secure ingestion gateway (mTLS, edge signing) + append-only encrypted storage
- [ ] Consent engine with scoped grants, revocation, and hash-chained ledger
- [ ] Consent-gated inference path with full provenance records
- [ ] Differential-privacy budget tracking and enforcement
- [ ] Federated learning across multiple nodes with DP aggregation
- [ ] Chaos + consent-bypass suite
- [ ] STRIDE threat model and security dossier
- [ ] Public EEG dataset integration and reproducible mental-state classification demo

---

## Author

**[@nickemma](https://github.com/nickemma)** — Building production-grade distributed systems, infrastructure, and secure-by-design platforms from first principles.

💼 Open to distributed systems, platform, backend, and security engineering roles at companies building serious systems.

<div align="center">
<a href="https://www.linkedin.com/in/techieemma/"><img src="https://img.shields.io/badge/linkedin-%23f78a38.svg?style=for-the-badge&logo=linkedin&logoColor=white" alt="Linkedin"></a>
<a href="https://twitter.com/techieemma"><img src="https://img.shields.io/badge/Twitter-%23f78a38.svg?style=for-the-badge&logo=Twitter&logoColor=white" alt="Twitter"></a>
<a href="https://github.com/nickemma/"><img src="https://img.shields.io/badge/github-%23f78a38.svg?style=for-the-badge&logo=github&logoColor=white" alt="Github"></a>
<a href="https://techieemma.medium.com/"><img src="https://img.shields.io/badge/Medium-%23f78a38.svg?style=for-the-badge&logo=Medium&logoColor=white" alt="Medium"></a>
<a href="mailto:nicholasemmanuel321@gmail.com"><img src="https://img.shields.io/badge/Gmail-f78a38?style=for-the-badge&logo=gmail&logoColor=white" alt="Gmail"></a>
</div>

---

**Building Systems, Building Faith — One Commit at a Time**

[⬆ Back to Top](#synapse-ai--consent-governed-neural-data--privacy-preserving-ml)
