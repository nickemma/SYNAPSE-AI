# TRADEOFFS — SYNAPSE-AI

**Purpose:** Document the conscious design choices made in SYNAPSE-AI, their costs, and why we chose them anyway.

**Last Updated:** June 24, 2026

---

## Core Architectural Tradeoffs

### Tradeoff 1: Synchronous Consent Verification vs. Eventual Consistency

**The Choice:** Every inference request synchronously checks the consent ledger *before* serving the model.

**What We Gain:**
- ✅ Immediate revocation: if a subject revokes consent at T=0, all inferences at T>0 are denied
- ✅ No race conditions: a revocation cannot be "overtaken" by an in-flight inference
- ✅ Regulatory-grade auditability: we can prove exactly what was consented to at the moment of inference
- ✅ Simple reasoning: the state of the ledger is the source of truth, not a cache

**What We Lose:**
- ❌ Latency: synchronous consent checks add ~10-50ms per inference (ledger lookup, hash chain verification, cache miss)
- ❌ Scalability bottleneck: the consent service becomes a chokepoint if many inferences hit an uncached grant
- ❌ Availability coupling: if the consent service is down, all inferences fail (no graceful degradation to "cached" state)
- ❌ Complexity: cache invalidation logic is subtle (TTL, revocation-triggered eviction, race conditions on cache vs. ledger)

**Cost-Benefit:**
| Cost | Severity | Mitigation |
| --- | --- | --- |
| Latency (10-50ms per request) | Medium | Cache with 60s TTL; makes 99% of requests cache-hits |
| Consent-service unavailability | High | Read replicas for ledger; async updates to secondary cache |
| Scalability at >1K inferences/sec | Medium | Shard consent ledger by subject ID; parallelize verification |

**Why This Trade:**
Neural data requires revocation to be *real*, not eventual. A subject revokes consent because they changed their mind *right now*, not "eventually." The regulatory requirement is clear: revocation must be honored immediately. We accept the latency cost.

**Alternative We Rejected:**
*Eventual consistency model: cache the consent decision locally on the inference service; update cache every 60 seconds from the ledger. If cache says "yes" but ledger says "no" (revocation), the revocation is delayed by up to 60 seconds.*
- Pro: inference latency drops to <1ms (cache-local lookup)
- Con: revocations are not immediate; a subject's revocation might be ignored for up to 60 seconds
- Con: regulatory risk; "we honored revocation eventually" is not the same as "revocation was immediate"
- **Rejected:** Neural data sensitivity demands immediate revocation

---

### Tradeoff 2: Append-Only Log vs. In-Place Mutations

**The Choice:** Neural samples and consent records are immutable once written. No deletion, no in-place update.

**What We Gain:**
- ✅ Tamper-evidence: modifying data requires rewriting the entire log (detectable via hash chain)
- ✅ Audit trail: every version of a record is preserved (no silent overwrites)
- ✅ Compliance: immutable audit logs are a regulatory gold standard
- ✅ Crash recovery: no complex undo/redo logic; the log *is* the truth
- ✅ Concurrency: multiple writers can append without coordination (CAS semantics on tail pointer)

**What We Lose:**
- ❌ Correction complexity: if a sample is mislabeled (e.g., tagged as "attention" but was "fatigue"), you can't fix it; you append a correction record instead
- ❌ Storage growth: every correction is a new record, so errors lead to log bloat
- ❌ Query complexity: queries must account for corrections (follow the chain of amendments for each record)
- ❌ Privacy revisions: if a subject asks to delete a prediction (right-to-forget), you can't; you append a tombstone record
- ❌ No in-place optimization: compacting or reordering the log requires creating a new log (offline operation)

**Cost-Benefit:**
| Cost | Severity | Mitigation |
| --- | --- | --- |
| Correction logic complexity | Low | Clients apply corrections when querying; it's tedious but not hard |
| Storage growth from corrections | Low | Log compaction runs weekly; old corrections are archived |
| Right-to-forget (GDPR) | High | Use tombstone records; data is not deleted but marked as inaccessible |
| Query latency on heavily-amended records | Low | Maintain amendment index; queries fast-follow the chain |

**Why This Trade:**
Append-only is the only architecture that makes tampering *detectable*. If we allowed in-place mutations, an attacker could modify data and we'd never know. The cost of managing corrections is acceptable.

**Alternative We Rejected:**
*Mutable log with transaction logs: allow in-place updates, but log every update to a separate transaction log for audit purposes.*
- Pro: queries are simpler (no correction chain-following)
- Con: audit trail is less comprehensive (transaction log might not capture all state changes)
- Con: risk of accidental data loss (DELETE statements in the transaction log)
- **Rejected:** Mutable logs are historically where tampering happens (nobody notices deletions)

---

### Tradeoff 3: Per-Subject Key Isolation vs. Single Platform Key

**The Choice:** Each subject's neural data is encrypted under a subject-specific key, not a shared platform key.

**What We Gain:**
- ✅ Isolation: if one subject's key is compromised, one subject's data is exposed (not all data)
- ✅ Revocation of access: we can rotate a subject's key without re-encrypting all platform data
- ✅ Key escrow: each subject's key is self-contained; doesn't depend on a global key ceremony
- ✅ Regulatory isolation: simpler to explain per-subject encryption to auditors

**What We Lose:**
- ❌ Key management complexity: we now manage N keys (one per subject) instead of 1
- ❌ KMS load: key lookups for every sample decrypt operation (KMS becomes a bottleneck)
- ❌ Key rotation overhead: rotating a subject's key requires either re-encrypting all their samples or maintaining multiple key versions
- ❌ Initialization cost: subject enrollment now includes key generation and secure delivery
- ❌ Operational overhead: backing up and recovering N keys is harder than backing up 1

**Cost-Benefit:**
| Cost | Severity | Mitigation |
| --- | --- | --- |
| KMS throughput | Medium | Local key cache with TTL; re-derive keys on miss (deterministic PBKDF2) |
| Key rotation operational load | Low | Schedule rotations during low-traffic periods; batch key rotation jobs |
| Key backup & recovery | Medium | Use HSM with geo-replication; encrypted key escrow with subject passphrase |
| Enrollment friction | Low | Key generation is automatic; subject doesn't see the complexity |

**Why This Trade:**
If a platform key is compromised, the entire corpus of neural data is exposed across all subjects. This is catastrophic. Per-subject keys means a compromise is scoped to one subject—serious, but not company-ending. The operational cost is worth the risk reduction.

**Alternative We Rejected:**
*Single platform key with per-subject sub-keys derived from it: one master key, subject-specific keys are derived.*
- Pro: key management is simpler; only master key needs HSM backup
- Con: master key compromise still exposes all subjects (sub-keys are derived, not independent)
- **Rejected:** Sub-keys derived from a master don't reduce the impact of master compromise

---

### Tradeoff 4: Federated Learning Only (No Centralized Training)

**The Choice:** Models are trained only via federated learning. Raw neural data never leaves the edge node.

**What We Gain:**
- ✅ Data residency: raw neural signals stay on the subject's device/node
- ✅ Trust boundary: the platform never sees raw data (only aggregated gradients)
- ✅ Regulatory advantage: no "data transfer" to justify; data is processed locally
- ✅ Subject consent scope: subjects don't need to consent to "centralized training"; only local training

**What We Lose:**
- ❌ Minimum cluster size: we need at least 3 nodes per federated round (for privacy via noising); can't train on single-node datasets
- ❌ Model latency: we can't iterate quickly; each round takes hours (data collection, training, aggregation, new model deployment)
- ❌ Training data diversity: we're limited to whatever samples happen to be on the nodes in this round; can't do active sampling
- ❌ Model expressiveness: models must be small enough to run locally; can't use large foundation models (training locally on a mobile device is infeasible)
- ❌ Gradient communication overhead: sending gradients over the network is expensive; bandwidth can be a bottleneck

**Cost-Benefit:**
| Cost | Severity | Mitigation |
| --- | --- | --- |
| Minimum 3 nodes per round | High | Start with public EEG datasets; recruit cohorts that meet min size |
| Iteration speed | Medium | Accept slower model development cycle; batch updates monthly instead of weekly |
| Model size constraints | High | Use small, efficient models (e.g., 1-5M params); avoid transformers |
| Bandwidth on gradient communication | Medium | Gradient compression; quantize before sending |

**Why This Trade:**
Centralizing neural data is the exact thing SYNAPSE-AI is trying to avoid. Federated learning is harder, but it's the only way to answer the core question: "How can AI operate on neural data without centralizing it?" We accept the constraints on training latency and model size.

**Alternative We Rejected:**
*Hybrid approach: collect data locally for federated training, but also allow "opt-in" centralized training for interested subjects.*
- Pro: enables richer models and faster iteration
- Con: introduces a second data path with different privacy guarantees
- Con: complicates consent logic (subjects must understand two different privacy models)
- **Rejected:** Hybrid models are where governance breaks down; the "opt-in" path becomes the easy path

---

### Tradeoff 5: Differential Privacy Budgets with Epsilon = 1.0 per Month

**The Choice:** Each subject has a strict privacy budget (epsilon = 1.0 per month). Once spent, no more inferences or training.

**What We Gain:**
- ✅ Formal privacy guarantee: epsilon quantifies the maximum leakage per subject per period
- ✅ Subject control: subjects know their privacy is budgeted and can see remaining balance
- ✅ Revocation analogy: privacy budget is similar to a revocation right; spending is voluntary (or so it seems)
- ✅ Regulatory clarity: we can justify privacy properties with a number, not a hand-wave

**What We Lose:**
- ❌ Inference latency increases over time: early inferences are noisy (high epsilon spent → high noise); later inferences are more accurate (low epsilon left → small noise, but budget nearly exhausted)
- ❌ User experience: subjects can't always get accurate inferences (some requests are denied due to budget exhaustion)
- ❌ Tightness: epsilon=1.0 is *tight* for a month of continuous monitoring; a subject who uses models every day will exceed budget in 10-15 days
- ❌ Re-budgeting complexity: when budget resets monthly, old budget is lost (subjects can't "carry over" unused budget)
- ❌ Interaction effects: multiple models draw from the same budget (using "attention research" model consumes budget for "fatigue monitoring" model)

**Cost-Benefit:**
| Cost | Severity | Mitigation |
| --- | --- | --- |
| Inference noise increasing | Low | Explain in docs that early inferences are noisier; budget is "front-loaded" |
| Budget exhaustion (subject locked out) | Medium | Alert subject at ε=0.7, 0.9, 0.95; offer manual reset for important queries |
| Tight budget for frequent users | High | Start with smaller population; gather feedback on realistic usage patterns |
| Re-budgeting UX | Medium | UI shows budget expiration date; allows manual reset requests |

**Why This Trade:**
Differential privacy is one of the few formal privacy guarantees we have. Without DP, a model could be inverted or membership-inferred-attacked with no limit. DP budgets enforce a hard bound on leakage. The tight budget is intentional—we're prioritizing privacy over convenience.

**Data Point:** In published federated learning studies (e.g., GBoard), epsilon=1.0 per day is considered tight but achievable. For a research platform with non-medical tasks, epsilon=1.0 *per month* is conservative.

**Alternative We Rejected:**
*No epsilon budget: allow unlimited inferences and training, with only noise injection.*
- Pro: no user friction; subjects can query as much as they want
- Con: no formal privacy bound; noise level is arbitrary
- Con: model inversion attacks are unbounded (attacker can query until they reverse-engineer the model)
- **Rejected:** Without budgets, DP is a hand-wave

---

### Tradeoff 6: Non-Medical, Public Datasets Only

**The Choice:** Models are trained on public EEG datasets (e.g., OpenBCI, PHYSIONET) for non-medical tasks (attention, fatigue, stress). Not for diagnosis.

**What We Gain:**
- ✅ Regulatory clarity: non-medical classification is not a diagnostic tool (no FDA approval required)
- ✅ Ethical simplicity: we're not making health decisions; subjects can ignore the output
- ✅ Data availability: public datasets are pre-collected and don't require new subject data
- ✅ Scope manageability: non-medical tasks have smaller feature spaces (easier to train, easier to secure)

**What We Lose:**
- ❌ Limited usefulness: attention/fatigue/stress classification is not diagnostically valuable (subjects likely know they're tired)
- ❌ Model accuracy: trained on population averages, won't be accurate for individuals with atypical signal morphology
- ❌ Market size: a "not diagnostic" tool has limited commercial appeal
- ❌ User recruitment: subjects won't enroll to get a tool that tells them something they already know
- ❌ Generalization: models trained on public data don't generalize to new population

**Cost-Benefit:**
| Cost | Severity | Mitigation |
| --- | --- | --- |
| Limited usefulness | High | Position as a "research platform" not a "diagnostic tool"; set expectations |
| Low accuracy on individuals | Medium | Be transparent about accuracy on public test sets; show calibration curves |
| Small user base | High | Target research institutions and wellness programs, not consumers |

**Why This Trade:**
Diagnostic systems are regulated (FDA, NMDA), require clinical trials, and carry liability. Non-diagnostic systems are not. By staying out of the diagnostic space, we can focus on getting the governance architecture right, without regulatory distraction. Once the platform matures, adding diagnostic models becomes easier.

**Future Path:**
Post-launch, a diagnostic model could be added *if* a research team invests in clinical validation. But the governance layer (SYNAPSE-AI) is diagnostic-agnostic.

---

### Tradeoff 7: 3-Node Minimum for Federated Rounds

**The Choice:** A federated learning round requires at least 3 nodes. Single-node or 2-node training is not allowed.

**What We Gain:**
- ✅ Privacy: with 3+ nodes, differential privacy bounds are meaningful (noise levels are well-understood)
- ✅ Fault tolerance: can tolerate 1 node failure and still aggregate
- ✅ Audit: harder to reverse-engineer a single subject's contribution with 3+ nodes

**What We Lose:**
- ❌ Startup friction: launching a federated round requires recruiting 3 nodes (3 subjects with data, devices, etc.)
- ❌ Slow iteration: if only 2 nodes are available, training is blocked until a 3rd node joins
- ❌ Use-case constraints: pilot studies or small cohorts can't benefit from federated training
- ❌ Resource utilization: if 10 nodes are available but only 3 are needed, the other 7 are idle

**Cost-Benefit:**
| Cost | Severity | Mitigation |
| --- | --- | --- |
| Startup friction | Medium | Pre-recruit pilot cohort of 5-10 subjects; organize training sessions |
| Slow iteration | Medium | Accept slower model development; schedule rounds monthly |
| Pilot-study friction | Medium | Offer centralized training for pilots (separate code path with different consent) |

**Why This Trade:**
Differential privacy only makes sense with population-level aggregation. A single-node model trained on one subject's data is not differentially private—the model is that subject's data. The 3-node minimum enforces privacy hygiene.

---

## Sensitivity Analysis: What If We Change These?

### What If We Lowered Epsilon to 0.5?
- Privacy guarantee is stronger (half the leakage budget)
- Inference latency increases further (noise is proportional to 1/ε)
- More users hit budget exhaustion (4-5 days of weekly usage instead of 10-15)
- User experience deteriorates; subject complaints increase
- **Verdict:** Too aggressive; would need to reduce inference rate or change reset period

### What If We Allowed In-Place Mutations?
- Storage system becomes more familiar (RDBMS-like)
- Corrections are cheaper (update, not append)
- Tampering becomes undetectable (no hash chain to break)
- Audit trail becomes unreliable (WHERE did that deletion come from?)
- Regulatory risk increases (auditors will ask "how do we know data wasn't silently modified?")
- **Verdict:** Not worth the risk; append-only is the right choice

### What If We Required Centralized Training?
- Model iteration speed increases (no waiting for nodes; train anytime)
- Model expressiveness increases (can use larger models)
- Risk: subjects' raw neural data is centralized (defeats the entire purpose)
- Regulatory risk: data residency violations, regulatory non-compliance
- **Verdict:** Defeats the core mission; non-negotiable

---

## Design Principles Embedded in These Tradeoffs

1. **Privacy Over Convenience**: When privacy and UX conflict, we choose privacy. Tight epsilon budgets and synchronous revocation are examples.

2. **Trustworthiness Over Feature Completeness**: We'd rather have a platform that does one thing (consent-gated inference) extremely well than a platform that does everything (diagnostic, prognostic, research, commercial) poorly.

3. **Immutability Over Simplicity**: Append-only logs are harder to reason about than mutable stores, but they're trustworthy.

4. **Federated Over Centralized**: The architectural friction of federated learning is worth the privacy gain.

5. **Formal Privacy Over Best-Effort**: DP budgets are strict and sometimes lock users out; but they're *provable*. Soft privacy controls are not.

---

## Unanswered Tradeoffs (Future Decisions)

### Tradeoff A: Support for Right-to-Forget (GDPR Art. 17)
**The Question:** Should subjects be able to request deletion of their data?
- Pro: GDPR right-to-forget is a regulatory requirement
- Con: append-only logs can't delete; can only tombstone
- Con: if a subject's data was used in training, can we "untrain" the model?
- **Status:** Deferred; will address post-MVP

### Tradeoff B: Central Auditor vs. Distributed Ledger
**The Question:** Should consent ledger be centralized, or replicated across nodes?
- Pro (centralized): simpler operations; single source of truth
- Con (centralized): single point of failure; auditors can pressure us to modify the ledger
- Pro (distributed): censorship-resistant; harder to modify
- Con (distributed): eventual consistency; consensus overhead
- **Status:** Deferred; current implementation is centralized with backups

### Tradeoff C: Real-Time Model Updates vs. Scheduled Retraining
**The Question:** Should models be updated continuously (every round that completes) or on a schedule (e.g., monthly)?
- Pro (continuous): models adapt faster to new data
- Con (continuous): more model versions; harder to track which model was used for which prediction
- Pro (scheduled): deterministic; easier to audit ("models updated on 1st of month")
- Con (scheduled): slower response to data drift
- **Status:** Deferred; current plan is scheduled monthly updates

---

## How to Use This Document

**For engineers:** Before implementing a feature, check if there's a tradeoff section. Understand what we're optimizing for.

**For auditors:** This document explains why we made hard choices. If a tradeoff looks wrong (e.g., "DP budgets are too tight"), this is where to challenge us.

**For product managers:** Understand the constraints. Asking for "real-time diagnosis on neural data" is asking to move our entire architecture. We've made conscious choices that preclude it.

---

## Feedback & Revisions

**This document is not final.** If you think a tradeoff is wrong, or if you have evidence that an alternative is better, open an issue and we'll reconsider.

Tradeoffs are decisions; decisions can be revisited.
