# THREAT MODEL — SYNAPSE-AI

**Last Updated:** June 24, 2026  
**Status:** In Development  
**Scope:** Neural data governance, consent-gated inference, federated learning with differential privacy

---

## Executive Summary

SYNAPSE-AI defends against **data theft, unauthorized inference, consent violation, privacy leakage via model inversion, and insider misuse**. It does *not* defend against **compromised devices, regulatory non-compliance, physical coercion, or adversarial training examples**. 

The system treats machine learning as a governed consumer subject to the same consent, encryption, and audit rules as a human user. This document explicitly names the adversaries we're defending against, the attack vectors we've mitigated, and the ones we haven't.

---

## Assets & Their Value

| Asset | Value | Owner |
| --- | --- | --- |
| **Raw neural signals** | Highest—closest to a direct brain readout; unique per person; non-rotatable | Subject (data donor) |
| **Consent ledger** | Critical—proof of who authorized what and when; tamper-evidence is non-negotiable | Subject + Platform |
| **Model weights** | High—trained on sensitive data; model inversion could leak subject info | Platform |
| **Prediction history** | High—patterns across predictions could enable membership inference | Subject |
| **Differential privacy budget** | Critical—once spent, no more valid inferences without re-budgeting | Subject |
| **Device credentials** (mTLS certs) | Critical—compromise allows spoofing edge devices | Subject |
| **Gateway service** | Critical—validates all ingestion; single point of entry | Platform |
| **Subject identity** | Critical—linking neural data to a real person breaks anonymity entirely | Subject |

---

## Threat Model: STRIDE

### **S — Spoofing**

#### Threat: Rogue Device Claims Subject Identity
**Scenario:** Attacker creates a fake edge device, obtains a certificate, and streams fabricated EEG data under a legitimate subject's ID.

**Mitigations:**
- mTLS device identity: every device must present a valid X.509 cert signed by the platform CA
- Device cert issuing happens *out-of-band* with subject verification (e.g., during enrollment, verified against their ID)
- Certificate pinning at the gateway: only known, registered device certs are accepted
- Per-device signing key: each sample is signed with the device's private key; the gateway validates the signature before storage

**Residual Risk:** If the platform CA is compromised, or if a subject's device private key is stolen, spoofing becomes possible. Mitigation: certificate revocation lists (CRLs) and frequent key rotation.

**Not Defended:** Physical theft of a device (the attacker now has the cert and the key). Mitigation is device-level (lock, biometric access), outside scope.

---

#### Threat: Rogue Requester Claims Model Identity
**Scenario:** An attacker submits an inference request claiming to be "mental-state-classifier@v2.3" when they're actually an unapproved model.

**Mitigations:**
- mTLS service identity: every model/consumer authenticates with its own cert
- Inference requests include both requester identity (mTLS cert) and model name
- The gateway verifies that the certificate CN matches the model name in the request
- Model versioning is strict: @v2.3 is locked to a specific set of hashes; code changes require a new version

**Residual Risk:** If an attacker obtains a legitimate model's mTLS cert, they can impersonate that model. Mitigation: cert revocation and audit alerts on unusual access patterns.

---

### **T — Tampering**

#### Threat: Attacker Modifies Neural Data in Storage
**Scenario:** An attacker with storage access (compromised operator, stolen backup) modifies EEG samples to hide or create evidence of a subject's condition.

**Mitigations:**
- Append-only encrypted log: no in-place mutations allowed; all writes are immutable
- AES-256-GCM authenticated encryption: any modification to a sample corrupts its authentication tag
- Per-sample HMAC: each sample record includes an HMAC chain to the previous record (Merkle-tree-like structure)
- WAL durability: writes are persisted to disk before acknowledgment to the client
- Tamper-evident audit trail: any read of an encrypted sample is logged with timestamp, requester, and subject

**Residual Risk:** If an attacker compromises the encryption keys, they can decrypt and re-encrypt modified data. Mitigation: key isolation per subject and regular key rotation audits.

#### Threat: Attacker Modifies Consent Ledger
**Scenario:** An attacker with storage access adds a fake consent grant (granting a rogue model access) or deletes a revocation to reactivate expired access.

**Mitigations:**
- Hash-chained consent ledger: every entry includes a hash of the previous entry; modifying an entry breaks the chain
- Append-only ledger: revocations and grants are *appended*, never deleted or overwritten
- Ledger commitment: the ledger root hash is published to an external log (or a Merkle tree is periodically signed by an off-platform authority)
- Synchronous verification: every inference request re-checks the ledger live (not cached); the current state is the source of truth

**Residual Risk:** If the entire ledger is replaced wholesale, the hash chain can be rebuilt from scratch. Mitigation: periodic Merkle root publication and external audit.

#### Threat: Attacker Modifies Prediction Records
**Scenario:** An attacker changes a prediction result post-hoc to hide or fabricate a finding.

**Mitigations:**
- Predictions are written to append-only storage, same as neural data
- Prediction records are hash-chained with the prediction timestamp and model version
- Predictions are cryptographically signed by the inference service before storage
- Audit trail links predictions to the authorising consent grant; modifying a prediction would require also modifying the grant, which breaks the ledger

**Residual Risk:** If the inference service itself is compromised, it can sign malicious predictions. Mitigation: separate inference service from storage; mTLS between them; audit alerts on high prediction rates per subject.

---

### **R — Repudiation**

#### Threat: Subject Denies Granting Consent
**Scenario:** A subject claims they never consented to a model running on their data, even though a grant exists in the ledger.

**Mitigations:**
- Hash-chained consent ledger is tamper-evident; you can prove what's in it
- Consent grants include subject identity, model identity, purpose, and timestamp
- Grants are issued only after explicit subject action (e.g., signing via a web UI, or biometric on the app)
- The ledger record includes the IP, device fingerprint, and session ID of the approving action
- Out-of-band notification: when a consent grant is issued, the subject receives an email/SMS notification with opt-out link

**Residual Risk:** A subject could claim their account was compromised when they issued the grant. Mitigation: multi-factor authentication on consent grant actions.

#### Threat: Platform Denies Operating on Data Correctly
**Scenario:** Platform claims data was encrypted and governed, but was actually exposed.

**Mitigations:**
- Prediction provenance records include the model, dataset, consent status, and timestamp
- Audit trail is externally queryable and hash-verified
- Regular third-party security audits of the logs
- Metrics exported to Prometheus: ingestion rate, consent denials, DP budget spend; these are independent of code

**Residual Risk:** If the entire audit trail is fabricated, repudiation is possible. Mitigation: ledger is signed periodically by an independent auditor.

---

### **I — Information Disclosure**

#### Threat: Model Inversion / Membership Inference
**Scenario:** An attacker trains on the model's outputs and reconstructs the training data (or infers whether a subject was in the training set).

**Mitigations:**
- **Differential privacy (on training):** Models are trained via federated learning with DP aggregation; gradients are clipped and Laplace noise is added before aggregation. Per-subject ε budget (e.g., ε=1.0) bounds how much a single subject can influence the model and how much an attacker can infer from outputs.
- **Differential privacy (on inference):** Each prediction has noise injected proportional to the query sensitivity; ε spend is tracked per subject per period.
- **Private predictions:** Predictions are not published in real-time; subjects cannot query the model's output for the same input twice (cache-aware DP).
- **Model versioning:** After ε budgets are exhausted, the model is retired and retrained with fresh DP budgets; an attacker cannot endlessly query the same model.

**Residual Risk:** Differential privacy is a formal guarantee *against a statistical adversary*, not against someone with direct access to the model weights. If an attacker trains their own model inversion attack on a DP-trained model, DP bounds the leakage, but doesn't prevent it. Mitigation: model weights are not published; only inference access is granted.

#### Threat: Data Exfiltration via Unencrypted Channels
**Scenario:** An attacker on the network intercepts neural signal transmission or consent ledger queries.

**Mitigations:**
- mTLS on all channels: every connection is encrypted and authenticated (edge device ↔ gateway, gateway ↔ storage, gateway ↔ inference service)
- AES-256-GCM encryption at rest: even if storage is stolen, data is encrypted
- No plaintext neural data ever transmitted off-device: samples are encrypted at the source
- WAL file encryption: the write-ahead log is encrypted before it hits disk

**Residual Risk:** If the mTLS certificates are compromised, or if a malicious network operator intercepts traffic, decryption is possible. Mitigation: certificate pinning and regular cert rotation audits.

#### Threat: Inference Service Logs Predictions in Plaintext
**Scenario:** An attacker with access to the inference service's logs (e.g., Docker logs, application logs) reads unencrypted predictions.

**Mitigations:**
- Inference requests and responses are never logged in plaintext
- Structured logs contain only: requester identity, subject ID (hashed), model name, consent decision (granted/denied), timestamp
- Actual prediction values are logged *only* to the append-only audit storage, which is encrypted
- Log rotation and encryption: application logs are rotated and encrypted after a short TTL

**Residual Risk:** If the inference service has a logging bug, predictions might leak. Mitigation: regular code review and automated log scanning for sensitive patterns.

#### Threat: Timing Side-Channel on Consent Verification
**Scenario:** An attacker observes the latency of inference requests and infers whether a subject has an active consent grant.

**Mitigations:**
- Consent checks are constant-time (no early-exit branches that vary on grant status)
- Inference latency is artificially padded to a fixed time (e.g., 100ms ± 10ms jitter) regardless of consent decision
- Failed requests return immediately with a denial (no lengthy timeout)

**Residual Risk:** High-resolution timing attacks (nanosecond-level) might still leak information. Mitigation: accept as acceptable risk; most network jitter dominates timing differences.

---

### **A — Availability**

#### Threat: Denial-of-Service on Ingestion Gateway
**Scenario:** An attacker floods the gateway with invalid EEG streams, consuming resources and preventing legitimate ingestion.

**Mitigations:**
- Rate limiting per device: each device ID is allowed N samples per second
- Request validation before acceptance: malformed samples are rejected at the mTLS layer
- Circuit breaker: if the storage service is full or slow, the gateway rejects new samples with a backpressure signal (HTTP 503)
- Auto-scaling: the gateway runs behind a load balancer and scales horizontally

**Residual Risk:** A botnet with stolen device credentials could still DoS. Mitigation: per-device rate limiting and anomaly detection (unusual spike in sample rate → alert).

#### Threat: Denial-of-Service on Consent Verification
**Scenario:** An attacker crafts many inference requests targeting different models, causing the consent service to become overloaded.

**Mitigations:**
- Consent checks are cached (TTL 60s): if the same subject + model + purpose grant is checked twice in 60s, the second check hits the cache
- Consent ledger is replicated for read availability (read replicas are async-updated)
- Request queuing with priority: consent denials (cache hits) are prioritized over grant verifications

**Residual Risk:** An attacker could craft requests for different subjects/models to bypass caching. Mitigation: global rate limiting across all inferences per model.

#### Threat: Federated Learning Round Never Completes (Node Failure)
**Scenario:** A node crashes mid-aggregation, leaving the system in a stuck state waiting for gradients.

**Mitigations:**
- Federated rounds have a timeout: if a node hasn't sent gradients within T seconds, it's marked as failed
- Partial aggregation: the system can aggregate gradients from N-1 nodes if one fails (assuming N ≥ 3)
- State checkpointing: the aggregator checkpoints gradients as they arrive; if it crashes, it can resume from the last checkpoint
- Automatic retry: the round can be restarted with remaining nodes

**Residual Risk:** If all nodes fail, or if N < 3 and one fails, the round is aborted. Mitigation: user is notified; they can retry later.

---

### **D — Denial of Service via Consent Exhaustion**

#### Threat: Subject's DP Budget Exhausted, No Further Inferences Allowed
**Scenario:** An attacker (or a legitimate model gone haywire) burns through a subject's privacy budget (ε=1.0), leaving the subject locked out of using models.

**Mitigations:**
- Budget burns are logged with inference request details
- Subject receives email alerts at ε=0.7, ε=0.9, ε=0.95
- Budget refresh can be requested by the subject (reset to ε=1.0 after a time period, e.g., monthly)
- Models can be separated by purpose: "attention research" models have separate budgets from "fatigue monitoring" models

**Residual Risk:** A subject could intentionally burn their budget. Mitigation: accept as user action, not a threat.

---

## Not Defended Against (Out of Scope)

### **1. Compromised Edge Device**
If a subject's EEG device is stolen and its private mTLS key is extracted, an attacker can spoof the device and stream fake data. **Mitigation:** Device-level security (lock, biometric), certificate revocation. This is the subject's responsibility.

### **2. Regulatory Non-Compliance**
The system enforces technical consent, but cannot enforce that a researcher actually uses data for the stated purpose. If a researcher receives inference results and uses them to make a medical diagnosis (when only "attention research" was consented to), the system cannot prevent it. **Mitigation:** Terms of service, audits, legal enforcement.

### **3. Adversarial Training Examples**
An attacker could craft EEG samples designed to fool the model. The system does not defend against this. **Mitigation:** Adversarial robustness is a model training concern, not a governance concern.

### **4. Side-Channel Attacks on Encrypted Storage**
If an attacker has physical access to the storage server, they could measure power consumption, timing, or electromagnetic emissions to infer patterns about the encrypted data. **Mitigation:** Physical security (locked data center), secure enclaves (hardware-level, out of scope).

### **5. Social Engineering of Researchers**
An attacker could trick a researcher into running a rogue model with legitimate credentials. **Mitigation:** Human factors training, organizational policy enforcement.

### **6. Quantum Computing**
RSA and ECDSA keys could be broken. ECC-based mTLS and AES-256-GCM would be vulnerable. **Mitigation:** Post-quantum cryptography (future work; not in initial roadmap).

### **7. Legal Compliance**
The system cannot defend against law enforcement with a warrant or a data subject's subpoena. If a court orders access, the data can be decrypted by the platform operator. **Mitigation:** Legal review, transparency reports.

---

## Attack Scenarios & Mitigations

### **Scenario 1: Insider Researcher Tries to Unlock Hidden Inferences**

**Actor:** Malicious researcher with valid model credentials  
**Attack:** Tries to infer what a subject's mental state was at a specific time by querying the model with synthetic EEG that matches known patterns  
**Defenses:**
- Query rate limiting: researcher can run at most N inferences per subject per day
- Prediction caching: the same input returns the same output; can't learn via repeated queries
- Consent scope includes "inference only" or "training only"—reading a subject's historical predictions requires explicit consent
- DP budget: each inference spends ε, exhausting budget quickly if many queries are made

**Verdict:** Attack is expensive and logged; detected via audit alerts.

---

### **Scenario 2: Attacker Tries to Revoke Consent, Then Re-add Without Audit Trail**

**Actor:** Storage operator with disk access  
**Attack:** Deletes a revocation record from the consent ledger, making an expired grant active again  
**Defenses:**
- Append-only ledger: deletions are impossible; can only append
- Hash chaining: deleting a record would break the chain; the next record's hash would no longer match
- Ledger integrity verification: on boot and periodically, the system verifies the hash chain; a broken chain causes an alert
- External publication: consent ledger root hash is published to a separate audit service; offline comparison detects tampering

**Verdict:** Attack leaves forensic evidence; would require colluding with the external audit service.

---

### **Scenario 3: Model Trainer Exfiltrates Training Data via Gradient Updates**

**Actor:** Malicious node operator in a federated learning round  
**Attack:** Crafts gradients that encode the raw training data, hoping to reverse-engineer it from the aggregated model  
**Defenses:**
- Differential privacy on gradients: before aggregation, each node clips gradients per-sample and adds Laplace noise; DP budget bounds how much information leaks
- Gradient clipping: norms are capped; outliers (which might encode rare data) are bounded
- Secure aggregation: instead of a central aggregator, gradients are homomorphically encrypted so no single party sees the raw gradients
- Anomaly detection: if a node's gradients are statistical outliers, the round is aborted and the node is flagged

**Verdict:** DP prevents exfiltration; secure aggregation is defense-in-depth.

---

### **Scenario 4: Subject Tries to Access Someone Else's Prediction History**

**Actor:** Malicious subject  
**Attack:** Uses their own valid credentials to query the prediction history of another subject  
**Defenses:**
- Audit trail is per-subject: each record includes subject ID
- Query authorization: access to prediction history requires either being the subject or having explicit delegation grant
- mTLS identity verification: the gateway verifies the requester's certificate; subject-A cannot claim to be subject-B

**Verdict:** Attack fails at authorization layer.

---

## Security Invariants

These must never be violated:

1. **No plaintext neural data off-device.** Every sample is encrypted before transmission.
2. **No inference without active consent.** Every request is checked against the consent ledger.
3. **Consent changes are append-only.** Revocations cannot be undone without a new grant.
4. **Privacy budgets are spent, never refunded.** ε spent cannot be "un-spent."
5. **Predictions are traceable.** Every result is linked to the authorising grant and the model version.
6. **The audit trail is tamper-evident.** Hash chaining and external publication prevent silent rewrites.
7. **Models are version-locked.** A model version's training data and parameters are immutable.

---

## Verification & Testing

- **Chaos testing:** Run consent-bypass scenarios (inference without consent, with expired consent, with revoked consent) and verify all are denied.
- **Fuzzing:** Fuzz the ingestion gateway with malformed EEG samples; verify none reach storage.
- **Cryptographic verification:** On startup, verify the hash chain of the consent ledger and the audit trail.
- **Timing analysis:** Measure consent-check latency; verify it's constant-time regardless of grant status.
- **Federated round fault injection:** Kill nodes mid-round; verify the system gracefully degrades or aborts.

---

## Compliance & Regulatory Mapping

| Regulatory Requirement | SYNAPSE-AI Control |
| --- | --- |
| Explicit consent required | Structured scoped grants in hash-chained ledger |
| Right to revocation | Immediate revocation stops inference; auditable |
| Data minimization | Models train on public datasets only; raw data stays on-node |
| Transparency | Prediction provenance records explain why a result was generated |
| Audit trail | Append-only, tamper-evident audit storage |
| Encryption at rest | AES-256-GCM per-subject key isolation |
| Encryption in transit | mTLS on all channels |
| Data subject access | Subject can query their own prediction history and consent grants |

---

## Future Mitigations (Post-MVP)

- [ ] Secure multi-party computation for federated aggregation (instead of relying on DP alone)
- [ ] Hardware security modules (HSM) for encryption key management
- [ ] Ledger publication to a blockchain or external immutable log service
- [ ] Post-quantum cryptography for mTLS and encryption
- [ ] Formal verification of the consent engine (state machine proofs)
- [ ] Differential privacy auditing tool (monitor DP budget spend in real-time)

---

## Threat Model Review Cadence

- **Every 6 months:** Review new attack vectors from ML security literature
- **After each major incident:** Update threat model; add new scenarios to chaos test suite
- **Annually:** Third-party security audit; update this document with findings

---

**Last reviewed:** [Date]  
**Next review:** [Date + 6 months]  
**Reviewer:** Security team + external auditor
